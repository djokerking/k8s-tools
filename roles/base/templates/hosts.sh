#!/bin/bash

{% for host in play_hosts %}
sed -i '/^{{ host }}/d' /etc/hosts
sed -i '$a {{ host }} {{ hostvars[host]['hostname'] }}' /etc/hosts
{% endfor %}
