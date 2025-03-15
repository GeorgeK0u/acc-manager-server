import socket
from threading import Thread, Lock
from time import sleep
import json
from lxml import etree as et
import os

UTF8 = 'utf-8'
CREATE_OP = 'C'
UPDATE_OP = 'U'
DEL_OP = 'D'
WRONG_CHARS = 5
SYNC_BC = 'sync_broadcast'
MANUAL_SYNC = 'manual_sync'
MANUAL_SYNC_END = 'manual_sync_end'
CLOSE_CONN = 'close_conn'
host = None
port = None
clients = None
lock = None
# XML
save_filename = None
xml_tree = None
xml_root = None
log_tag_name = None
latest_acc_name_tag_name = None
latest_extra_info_tag_name = None
latest_pwd_tag_name = None
# Create/Update op
log_item_tag_name = None
acc_name_tag_name = None
extra_info_tag_name = None
pwd_tag_name = None

def send_msg(conn, msg):
    try:
        msg = msg.encode(UTF8)
        conn.send(msg)
        return True
    except:
        return False

def sync_connected_devices(msg, sender):
    for c in clients: 
        if c == sender:
            continue
        # If msg to a client fails to be sent, it just fails to be sent 
        send_msg(c, msg)

def convert_to_json_string(list_):
    json_string = json.dumps(list_)
    return json_string

def convert_to_list(json_string):
    list_ = json.loads(json_string) 
    return list_

def get_log_index(logs, enc_cur_acc_name):
    for i in range(len(logs)):
        log = logs[i]
        enc_latest_acc_name = log[0].text
        if enc_latest_acc_name != enc_cur_acc_name:
            continue
        return i
    return -1

def encrypt(text):
    enc_text = ''
    for ch in text:
        enc_ch = chr(ord(ch)+WRONG_CHARS)
        enc_text += enc_ch
    return enc_text

def decrypt(text):
    dec_text = ''
    for ch in text:
        dec_ch = chr(ord(ch)-WRONG_CHARS)
        dec_text += dec_ch
    return dec_text

def get_client_acc_index_of_log(client_enc_accs, latest_acc_send_status_list, log_tag):
    # get all log item tags
    log_item_tags = log_tag.findall(log_item_tag_name)
    # log latest enc values
    log_latest_enc_acc_name = log_tag[0].text
    log_latest_enc_extra_info = log_tag[1].text
    log_latest_enc_pwd = log_tag[2].text
    log_latest_values = [log_latest_enc_acc_name, log_latest_enc_extra_info, log_latest_enc_pwd]
    for i in range(len(client_enc_accs)):
        # log for this client account is already found
        if latest_acc_send_status_list[i] == 0:
            continue
        # Get client acc
        client_enc_acc = client_enc_accs[i]
        for log_item_tag in log_item_tags:
            # Get log item values
            log_enc_acc_name = log_item_tag[0].text
            log_enc_extra_info = log_item_tag[1].text
            log_enc_pwd = log_item_tag[2].text
            log_item_enc_acc = [log_enc_acc_name, log_enc_extra_info, log_enc_pwd]
            # Check if log acc version matches the client cur version
            if log_item_enc_acc == client_enc_acc:
                # Debug
                print(f'Found match for log {log_latest_values}')
                return i
    # No client acc found for this log
    print(f'No match found for log {log_latest_values}')
    return -1
            
def commit():
    xml_tree.write(save_filename)

def handle_conn(conn, client_addr):
    clients.append(conn)
    client_enc_accs = []
    open_ = True
    while open_:
        try:
            client_msg = conn.recv(1024).decode(UTF8)
            # Close connection
            if client_msg == CLOSE_CONN:
                print(f'Received close signal from client {client_addr}')
                open_ = False
            elif client_msg.__contains__(SYNC_BC):
                print(f'Received sync broadcast msg: {client_msg} from client {client_addr}')
                client_msg_og = client_msg
                # Convert msg back to list
                sync_msg = convert_to_list(client_msg)
                op = sync_msg[1]
                # Lock shared resource
                lock.acquire()
                # Add an extra array with all encrypted acc details in case the client doesn't have the account and needs to be created 
                if op == UPDATE_OP:
                    # Get latest details from XML
                    enc_prev_acc_name = sync_msg[2]
                    logs = xml_root.findall(log_tag_name)
                    log_index = get_log_index(logs, enc_prev_acc_name)
                    log_tag = logs[log_index]
                    # latest/prev acc details
                    enc_latest_acc_name = log_tag[0].text
                    enc_latest_extra_info = log_tag[1].text
                    enc_latest_pwd = log_tag[2].text
                    enc_latest_details = [enc_latest_acc_name, enc_latest_extra_info, enc_latest_pwd]
                    # Get updated details
                    enc_update_details = sync_msg[3:]
                    for enc_update_detail_arr in enc_update_details:
                        update_detail_index = int(decrypt(enc_update_detail_arr[0]))
                        enc_update_detail_value = enc_update_detail_arr[1]
                        enc_latest_details[update_detail_index] = enc_update_detail_value
                    # Add latest/prev details arr for the create acc possibility before updated details arr
                    sync_msg.insert(3, enc_latest_details)
                    client_msg = convert_to_json_string(sync_msg)
                # send broadcast sync msg to clients
                sync_connected_devices(client_msg, conn)
                # Get original msg
                sync_msg = convert_to_list(client_msg_og)
                sync_msg.pop(0)
                sync_msg.pop(0)
                # Update XML
                if op == CREATE_OP:
                    enc_acc_name, enc_extra_info, enc_pwd = sync_msg
                    log_tag = et.SubElement(xml_root, log_tag_name)
                    # Set latest acc name, extra info and pwd
                    latest_acc_name_tag = et.SubElement(log_tag, latest_acc_name_tag_name)
                    latest_acc_name_tag.text = enc_acc_name
                    latest_extra_info_tag = et.SubElement(log_tag, latest_extra_info_tag_name)
                    latest_extra_info_tag.text = enc_extra_info
                    latest_pwd_tag = et.SubElement(log_tag, latest_pwd_tag_name)
                    latest_pwd_tag.text = enc_pwd
                    log_item_tag = et.SubElement(log_tag, log_item_tag_name)
                    acc_name_tag = et.SubElement(log_item_tag, acc_name_tag_name)
                    acc_name_tag.text = enc_acc_name
                    extra_info_tag = et.SubElement(log_item_tag, extra_info_tag_name)
                    extra_info_tag.text = enc_extra_info
                    pwd_tag = et.SubElement(log_item_tag, pwd_tag_name)
                    pwd_tag.text = enc_pwd
                elif op == UPDATE_OP:
                    enc_cur_acc_name = sync_msg.pop(0)
                    logs = xml_root.findall(log_tag_name)
                    log_index = get_log_index(logs, enc_cur_acc_name)
                    log_tag = logs[log_index]
                    log_item_tag = et.SubElement(log_tag, log_item_tag_name)
                    acc_name_tag = et.SubElement(log_item_tag, acc_name_tag_name)
                    extra_info_tag = et.SubElement(log_item_tag, extra_info_tag_name)
                    pwd_tag = et.SubElement(log_item_tag, pwd_tag_name)
                    for enc_update_value_list in sync_msg:
                        enc_index, enc_value = enc_update_value_list
                        # Update latest values
                        index = int(decrypt(enc_index))
                        log_tag[index].text = enc_value
                    # set update version values
                    acc_name_tag.text = log_tag[0].text
                    extra_info_tag.text = log_tag[1].text
                    pwd_tag.text = log_tag[2].text
                elif op == DEL_OP:
                    enc_acc_name = sync_msg.pop()
                    logs = xml_root.findall(log_tag_name)
                    log_index = get_log_index(logs, enc_acc_name)
                    log_tag = logs[log_index]
                    xml_root.remove(log_tag)
                # Commit XML changes
                commit()
                # Unlock shared resource
                lock.release()
            elif client_msg.__contains__(MANUAL_SYNC):
                # Lock shared resource
                lock.acquire()
                if client_msg != MANUAL_SYNC_END: 
                    # Convert back to list
                    client_msg = convert_to_list(client_msg)
                    # Remove signal part
                    client_msg.pop(0)
                    enc_acc = client_msg
                    # Store acc in client thread global list
                    # to only send relevant sync msgs
                    client_enc_accs.append(enc_acc)
                # Manual sync client end signal
                else:
                    latest_acc_send_status_list = []
                    for i in range(len(client_enc_accs)):
                        latest_acc_send_status_list.append(1)
                    logs = xml_root.findall(log_tag_name)
                    for i in range(len(logs)):
                        log_tag = logs[i]
                        log_latest_enc_acc_name = log_tag[0].text
                        log_latest_enc_extra_info = log_tag[1].text
                        log_latest_enc_pwd = log_tag[2].text
                        # Check if there is a client acc with the acc name being one of the log item names 
                        client_acc_index = get_client_acc_index_of_log(client_enc_accs, latest_acc_send_status_list, log_tag)
                        if client_acc_index == -1:
                            # Send create sync msg for accounts not existing on the client
                            msg = [MANUAL_SYNC, CREATE_OP, log_latest_enc_acc_name, log_latest_enc_extra_info, log_latest_enc_pwd]
                            msg_json_string = convert_to_json_string(msg)
                            ok = send_msg(conn, msg_json_string)
                            print(f'Account {log_tag[0].text} did not exist on the client. Sending a create...')
                            # Failed to sent msg
                            if not ok:
                                open_ = False
                                print('Failed to complete sync. Connection got lost')
                                break
                        else:
                            # Update server log acc status
                            latest_acc_send_status_list[client_acc_index] = 0
                            # Check if need to send the acc
                            client_enc_acc = client_enc_accs[client_acc_index]
                            log_latest_values = [log_latest_enc_acc_name, log_latest_enc_extra_info, log_latest_enc_pwd]
                            # Already up to date
                            if log_latest_values == client_enc_acc:
                                print('Latest version of this account already exists')
                                continue
                            # Send
                            client_enc_cur_acc_name = client_enc_acc[0]
                            msg = [MANUAL_SYNC, UPDATE_OP, client_enc_cur_acc_name]
                            for i in range(len(client_enc_acc)):
                                client_enc_cur_value = client_enc_acc[i]
                                print(f'DECRYPTED CUR VALUE {decrypt(client_enc_cur_value)}')
                                enc_latest_value = log_latest_values[i]
                                print(f'DECRYPTED UPDATED VALUE {decrypt(enc_latest_value)}')
                                if client_enc_cur_value == enc_latest_value:
                                    continue
                                print(f'Updating value index: {i}')
                                enc_update_index = encrypt(str(i))
                                msg.append([enc_update_index, enc_latest_value])
                            msg_json_string = convert_to_json_string(msg)
                            print('Sending an update for this account latest version...')
                            ok = send_msg(conn, msg_json_string)
                            # Failed to sent msg
                            if not ok:
                                open_ = False
                                print('Failed to complete sync. Connection got lost')
                                break
                        # Sleep for 100 ms
                        sleep(1)
                    # Connection still open 
                    if open_:
                        for i in range(len(latest_acc_send_status_list)):
                            if latest_acc_send_status_list[i] == 0:
                                continue
                            # Acc doesn't exist on server save file so delete it
                            client_enc_acc_name = client_enc_accs[i][0]
                            msg = [MANUAL_SYNC, DEL_OP, client_enc_acc_name]
                            msg_json_string = convert_to_json_string(msg)
                            ok = send_msg(conn, msg_json_string)
                            # Debug
                            client_acc_name = decrypt(client_enc_acc_name)
                            print(f'Account {client_acc_name} doesn\'t exists on latest XML save file. Deleting it...')
                            # Failed to sent msg
                            if not ok:
                                open_ = False
                                print('Failed to complete sync. Connection got lost')
                                break
                            sleep(1)
                    # Connection still open 
                    if open_:
                        # Send server manual sync end signal 
                        print('Manual sync completed')
                        ok = send_msg(conn, MANUAL_SYNC_END)
                        # Failed to sent msg
                        if not ok:
                            open_ = False
                            print('Failed to complete sync. Connection got lost')
                    # Clear temp stored list
                    client_enc_accs = []
                    latest_acc_send_status_list = []
                # Unlock shared resource
                lock.release()
            else:
                print(f'Client says {client_msg}')
        except Exception as e:
            print(f'Error occured on receiving message from client {client_addr}. Exception: {e}')
            open_ = False
    # send close connection msg to client
    send_msg(conn, CLOSE_CONN)
    # Close connection from server side
    conn.close()
    print('Connection closed from server side')
    print(f'Client {client_addr} disconnected')
    clients.remove(conn)

def init():
    global host, port, clients, lock
    global save_filename, xml_tree, xml_root, log_tag_name, latest_acc_name_tag_name, latest_extra_info_tag_name, latest_pwd_tag_name
    global log_item_tag_name, acc_name_tag_name, extra_info_tag_name, pwd_tag_name
    # read ip and port from connection json file
    conn_json_file_dir = r'..\conn.json'
    with open(conn_json_file_dir, 'r') as file:
        data = json.load(file)
        host = data['server_private_ip']
        port = int(data['port'])
    clients = []
    lock = Lock()
    # XML
    save_filename = 'save.xml'
    xml_tree = et.parse(save_filename)
    xml_root = xml_tree.getroot()
    log_tag_name = 'log'
    latest_acc_name_tag_name = 'latest-acc-name'
    latest_extra_info_tag_name = 'latest-extra-info'
    latest_pwd_tag_name = 'latest-pwd'
    log_item_tag_name = 'log-item'
    acc_name_tag_name = 'acc-name'
    extra_info_tag_name = 'extra-info'
    pwd_tag_name = 'pwd'

def listen():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    print('Listening...')
    # Accept clients and handle each connection on a seperate thread
    while True:
        try:
            conn, client_addr = server.accept()
            print(f'Client {client_addr} connected')
            # Create conn thread
            conn_thread = Thread(target=lambda:handle_conn(conn, client_addr))
            conn_thread.start()
        except Exception as e:
            print(f'An exception occured: {e}')
            break

init()
listen()
