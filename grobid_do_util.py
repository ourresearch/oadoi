import os
import time
from typing import List

import digitalocean
import paramiko
import requests

DO_API_KEY = os.getenv('DO_API_KEY_NOLAN')
GROBID_LB_NAME = 'sfo3-load-balancer-01'
GROBID_LB_ID = '462456b5-49d2-42be-a3a2-c02d0d1a81df'
OPENALEX_PROJECT_ID = '1d90aa5b-22a4-4d8c-9b8d-925bd9b382ec'
GROBID_SNAPSHOT_ID = '153089421'
SSH_KEY_ID = 38724864

manager = digitalocean.Manager(token=DO_API_KEY)
project = manager.get_project(OPENALEX_PROJECT_ID)
lb = manager.get_load_balancer(id=GROBID_LB_ID)

grobid_droplets = manager.get_all_droplets(tag_name='grobid')


def add_grobid_droplet():
    global grobid_droplets
    ssh_key = manager.get_ssh_key(SSH_KEY_ID)
    droplet = digitalocean.Droplet(token=DO_API_KEY,
                                   ssh_keys=[ssh_key],
                                   name=f'grobid-pdf-parser-{int(time.time())}',
                                   image=GROBID_SNAPSHOT_ID,
                                   size_slug='s-8vcpu-32gb-640gb-intel',
                                   monitoring=True,
                                   tags=['grobid'],
                                   region=[lb.region['slug']])
    droplet.create()
    project.assign_resource([f'do:droplet:{droplet.id}'])
    time.sleep(2 * 60)
    lb.add_droplets([int(droplet.id)])
    grobid_droplets = manager.get_all_droplets(tag_name='grobid')


def run_grobid_ssh_cmds(cmds: List[str], log_stdout: bool = False):
    droplets = manager.get_all_droplets(tag_name='grobid')
    for droplet in droplets:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(droplet.ip_address, username='root',
                    key_filename='./unpaywal-ec2-keypair.cer')
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            if log_stdout:
                for line in stdout:
                    print(f'{line.strip()}')


def restart_grobid_containers():
    run_grobid_ssh_cmds(['systemctl restart grobid'], log_stdout=True)


def start_grobid_containers():
    run_grobid_ssh_cmds(['systemctl start grobid'], log_stdout=True)


def stop_grobid_containers():
    run_grobid_ssh_cmds(['systemctl stop grobid'], log_stdout=True)


def restart_grobid_droplets():
    for droplet in grobid_droplets:
        droplet.power_cycle()


def droplet_status(ip):
    url = f'http://{ip}'
    try:
        r = requests.get(url, timeout=30)
        return r.ok
    except Exception as e:
        return False

def restart_down_servers():
    for droplet in grobid_droplets:
        if not droplet_status(droplet.ip_address):
            droplet.power_cycle()
            print(f'Restarted droplet {droplet.ip_address}')
        else:
            print(f'Droplet {droplet.ip_address} OK')


if __name__ == '__main__':
    restart_down_servers()
    # stop_grobid_containers()
    # start_grobid_containers()
    # stop_grobid_containers()
    # restart_grobid_droplets()
    # add_grobid_droplet()
