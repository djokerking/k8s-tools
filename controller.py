#!/usr/bin/env python
#encoding:utf-8
# desc: k8s自动化部署脚本

import argparse
import inspect
import os
import sys
import subprocess
import IPy
import time
import datetime
import tarfile
import __main__ as main

workdir = os.path.dirname(os.path.realpath(__file__))
os.environ['PATH'] = os.environ.get('PATH') + ':' +  workdir + '/bin'
os.environ['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

sys.path.append(workdir + '/modules')
import MyConfigParser
from jsonContext import *

# 常量
hostsConf = 'hosts'

# 函数
def cmdRcode(cmd):
    return os.system(cmd)

def cmdRtext(cmd):
    return os.popen(cmd).read()

def is_ip(**address):
    for ip in address.keys():
        try:
            IPy.IP(address[ip])
        except Exception as e:
            return False, ip + ": 地址不合法"
    return True,None

def cmdrun(shell):
    cmd = subprocess.Popen(shell, stdin=subprocess.PIPE, stderr=sys.stderr, close_fds=True,
                           stdout=sys.stdout, universal_newlines=True, shell=True, bufsize=1)
    cmd.communicate()
    if  cmd.returncode != 0: sys.exit(4)

def curTime():
    return time.strftime("%Y%m%d_%H%M%S", time.localtime()) 

# 解压大于100M的文件,因为大于100M无法上传到github
def init_untargt():
    print "解压大于100M的文件,因为大于100M无法上传到github"
    for root, dirs, files in os.walk(os.path.join(workdir, 'roles/kubernetes/files')):
        for f in files:
            if f.endswith('.tar.gz'):
                t = tarfile.open(os.path.join(root,f))
                t.extractall(path = os.path.join(workdir, 'roles/kubernetes/files'))
    
def init_createSSHKey():
    print "创建ssh key ....."
    if not os.path.exists(os.path.join(workdir, 'ssl/id_rsa')):
        cmdrun("ssh-keygen -t rsa -N '' -f " + os.path.join(workdir, 'ssl/id_rsa'))
    cmdrun('cp -f ' + os.path.join(workdir, 'ssl/{id_rsa,id_rsa.pub}') + ' ' + os.path.join(workdir, 'roles/base/files'))

def initCA(name, dst=None):
    os.chdir(os.path.join(workdir, 'ssl'))
    if name == 'ca':
        cmdrun('cfssl gencert -initca ca-csr.json | cfssljson -bare ca')
    elif os.path.exists(name + '-csr.json'):
      cmdrun('rm -rf %s.csr %s-key.pem %s.pem' % (name, name, name))
      cmdrun('cfssl gencert -ca=ca.pem \
      -ca-key=ca-key.pem \
      -config=ca-config.json \
      -profile=kubernetes %s-csr.json | cfssljson -bare %s' % (name, name))
    os.chdir(workdir)
    if dst == None: dst = name
    cmdrun('cp -f ssl/{%s.pem,%s-key.pem} roles/%s/files' % (name, name, dst))

def write(text, filename, flag=None, var=None):
    with open(filename, 'w') as f:
        textList = []
        if flag == None and var == None:
            f.write(text)
        else:
            for line in text.split(os.linesep):
                if flag in line:
                    textList.append(line)
                    for v in var:
                        textList.append('    "%s",' % v)
                    line = os.linesep.join(textList)
                f.write(line + os.linesep)

def initJsonFile(args):
    print "生成json文件......"
    os.chdir(os.path.join(workdir, 'ssl'))
    write(ca_csr_json, 'ca-csr.json')
    write(ca_config_json, 'ca-config.json')
    
    if args.etcd == None:
        etcdHosts = args.hosts.split(',')[:3]
    else:
        etcdHosts = []
        for e in args.etcd.split(','):
            etcdHosts.append(args.nameHostDir.get(e))
    etcdHosts = etcdHosts + args.etcd.split(',')
    write(etcd_csr_json, 'etcd-csr.json', 'hosts', etcdHosts)

    if args.master == None:
        ips = args.hosts.split(',')[:3]
    else:
        ips = []
        for i in args.master.split(','):
            ips.append(args.nameHostDir.get(i))
    vip = args.vip
    ips.append(vip)
    ips = ips + args.master.split(',')
    write(kubernetes_csr_json, 'kubernetes-csr.json', 'hosts', ips)
    write(admin_csr_json, 'admin-csr.json')
            
def init_all():
    os.chdir(workdir)
    print "准备基础环境......"
    cmdrun('ansible-playbook -i hosts roles/base.yaml')
    print "部署docker环境......"
    cmdrun('ansible-playbook -i hosts roles/docker.yaml')
    print "创建ca、etcd所需证书......"
    initCA('ca', dst='etcd')
    initCA('etcd')
    print "部署etcd环境......"
    cmdrun('ansible-playbook -i hosts roles/etcd.yaml')
    print "创建k8s所需证书......"
    initCA('kubernetes')
    initCA('admin', dst='kubernetes')
    print "部署k8s环境......"
    cmdrun('ansible-playbook -i hosts roles/kubernetes.yaml')

def clean_env():
    print "清理环境......"
    for root, dirs, files in os.walk(os.path.join(workdir, 'ssl')):
        for f in files:
            if not f.endswith('.json'):
                os.remove(os.path.join(root, f))
    
def action_install(args):
    if args.action != "install": return
    # 获取参数
    if args.hosts is None: raise Exception("主机列表不能为空")
    if args.names is None: raise Exception("主机名列表不能为空")

    hosts = args.hosts.split(',')
    names = args.names.split(',')
    if len(hosts) != len(names): raise Exception("主机ip和名称数量不匹配")
    nameHostDir = dict(zip(names, hosts))
    args.nameHostDir = nameHostDir

    if args.etcd is not None: 
        etcd = args.etcd.split(',')
        if len(etcd) != 3: 
            print "etcd所在主机列表数不为3，自动选择前三个"
            etcd = names[:3]  
    else:
        etcd = names[:3]
    if not set(etcd).issubset(set(names)) : raise Exception("etcd所在列表名不在主机列表中")

    if args.keepalive:
        if args.master is not None:
            master = args.master.split(',')
        else:
            master = names[:3]
    else:
        master = names[:1]
    if not set(master).issubset(set(names)): raise Exception("master所在列表名不在主机列表中")

    vip = args.vip
    # 生成主机部分
    if os.path.exists(os.path.join(workdir, hostsConf)):
        os.rename(os.path.join(workdir, hostsConf), os.path.join(workdir, '.' + hostsConf + '_' + curTime()))

    mcp = MyConfigParser.MyConfigParser()

    mcp.add_section('k8s')
    for ip in hosts:
        mcp.set('k8s', ip + '_r_', 'hostname=' + names[hosts.index(ip)])

    mcp.add_section('k8s:vars')
    mcp.set('k8s:vars', 'ansible_ssh_user_e_', 'root') 
    mcp.set('k8s:vars', 'ansible_ssh_pass_e_', '123456') 
    mcp.set('k8s:vars', 'master_e_', ','.join(master) )
    mcp.set('k8s:vars', 'etcd_e_', ','.join(etcd) )
    if args.keepalive:
        mcp.set('k8s:vars', 'k8svip_e_', vip) 
    mcp.write(open(os.path.join(workdir, hostsConf), 'w'))

    clean_env()
    initJsonFile(args)
    for funcName in main.__dict__.keys():
        if funcName.startswith("init_"): getattr(main, funcName)()

def action_addnode(args):
    if args.action != "addnode": return
    hosts = args.hosts

def action_removenode(args):
    if args.action != "removenode": return
    hosts = args.hosts

def action_start(args):
    if args.action != "start": return

def action_stop(args):
    if args.action != "start": return
    print "stop args"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="自动安装和部署kubernetes(k8s)脚本,最少需要三个节点部署.",
                                     prog="controller.py",
                                     usage="%(prog)s install|addnode|removenode|start|stop [options...]")
    parser.add_argument('action', choices=['install', 'addnode','removenode','start','stop'],
                                  help="当前操作,支持安装install、添加计算节点addnode、移除计算节点removenode、启动start、关闭stop")
    parser.add_argument('--hosts',  metavar="ip1,ip2,ip3", required=True, help="主机列表,用分号隔开,如: ip1,ip2,ip3...")
    parser.add_argument('--names',  metavar="node1,node2,node3", help="主机名,需要一一对应,用分号隔开,如: node1,node2,node3...")
    parser.add_argument('--etcd', '-e', metavar="node1,node2,node3", help="etcd所在主机名列表,默认前三个,用分号隔开,如: node1,node2,node3...默认前三个节点")
    parser.add_argument('--keepalive', '-ka', action='store_true', help="是否开启k8s高可用,默认关闭")
    parser.add_argument('--master', '-m', metavar="node1,node2,node3", help="master所在主机名列表,默认前三个, 用分号隔开,如: node1,node2,node3...高可用开启时生效")
    parser.add_argument('--vip', metavar='vip',help="指定集群apiserver的虚IP,高可用开启时生效")
    args = parser.parse_args()
    # 执行所有action函数
    for funcName in main.__dict__.keys():
        if funcName.startswith("action_"): getattr(main, funcName)(args)
