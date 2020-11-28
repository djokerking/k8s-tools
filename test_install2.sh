./controller.py  install \
--hosts 192.168.31.11,192.168.31.12,192.168.31.13,192.168.31.14,192.168.31.15,192.168.31.16 \
--name node11,node12,node13,node14,node15,node16 \
--etcd node11,node12,node13 \
--keepalive \
--master node11,node12,node13 \
--vip 192.168.31.19 
