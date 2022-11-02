import pika, sys, os
from time import sleep 
from utilities import primary_tools as pt
from datetime import datetime
from os import path
from multiprocessing import Queue, Process
import functools


def manage_rabbit_connection(fn):
    @functools.wraps(fn)
    def wrapper(*args, target_name):
        connection = pika.BlockingConnection(pika.ConnectionParameters(target_name))
        
        fn(*args, connection)
        
        connection.close()
    return wrapper



@manage_rabbit_connection
def send_to_queue(queue_name, value, connection):
    
    channel = connection.channel()

    channel.queue_declare(queue=queue_name)

    channel.basic_publish(exchange='', routing_key=queue_name, body=value)
    
    print(f"{value} sent to queue")




def scan_folder(folder_path, target_object, scan_time=3, current_size=None, current_ts=None):
    get_target_object=pt.get_folder_object_from_dir if target_object=='folder' else pt.get_file_object_from_dir
    current_size = len(get_target_object(folder_path)) if current_size is None else current_size
    current_ts= datetime.now().timestamp() if current_ts is None else current_ts
    
    
    folder_scan_dict={
        'current_size':current_size,
        'current_ts':current_ts
    }
    
   
    def get_folder_size(folder_path):
        
        return len(get_target_object(folder_path))
    
        
    def get_new_target_created():
        
        folder_collect=get_target_object(folder_path)
            
        return [folder for folder in folder_collect if path.getctime(folder.path) > folder_scan_dict['current_ts']]
        
        
        
    def r_get_earliest_ts_from_new_target(target_object_list, current_ts, save_list=None, earliest_ts=None):
        save_list=target_object_list.copy() if save_list is None else save_list
        earliest_ts=current_ts if earliest_ts is None else earliest_ts
    
        if len(save_list)==0:
            return earliest_ts
        else:
            current_target=save_list.pop(0)
                
            target_ctime=path.getctime(current_target.path)
                
            earliest_ts= target_ctime if earliest_ts < target_ctime else earliest_ts
                
            return r_get_earliest_ts_from_new_target(target_object_list, current_ts, save_list, earliest_ts)

            
    while True:
                                
        new_size=get_folder_size(folder_path)
                
        if new_size > folder_scan_dict['current_size']:
                
            target_object_list=get_new_target_created()
                    
            for target_object in target_object_list:
                
                send_to_queue('files', target_object.path, target_name='rabbit')
                    
            folder_scan_dict['current_size']=new_size
                    
            folder_scan_dict['current_ts']=r_get_earliest_ts_from_new_target(target_object_list, folder_scan_dict['current_ts'])  
                   
        sleep(scan_time)
  


def create_subfolder_scan_process(folder_path):     
        
    process = Process(target=scan_folder, args=(folder_path, 'file'))
    process.start()
    




def callback(ch, method, properties, body):
    
    print(f"Received from queue {body}")
    
    create_subfolder_scan_process(body)
    
    
        
        
def main():
    
    print('init_connect')
    
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbit'))
    
    channel = connection.channel()

    channel.queue_declare(queue='subdir')


    channel.basic_consume(queue='subdir', on_message_callback=callback, auto_ack=True)
    

    print(' [*] Waiting for messages. To exit press CTRL+C')
    
    
    channel.start_consuming()
    
    
    
    
    
    
    

if __name__ == '__main__':
    # sleep(60)
    print('receiver')
    main()