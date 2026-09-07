#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
from ansible.module_utils.basic import AnsibleModule

UUID_RE=re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
SAFE_PATH_RE=re.compile(r"^/[A-Za-z0-9._:/-]+$")
SERVER_XML="/etc/tomcat/server.xml"
STATE_ROOT="/var/lib/layersentryd/state"

def atomic_write(path: str,data: bytes,mode: int)->None:
    directory=os.path.dirname(path);fd,tmp=tempfile.mkstemp(prefix=".layersentry-tomcat-",dir=directory)
    try:
        os.fchmod(fd,mode);os.write(fd,data);os.fsync(fd);os.close(fd);fd=-1;os.replace(tmp,path);dfd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if fd>=0:os.close(fd)
        if os.path.exists(tmp):os.unlink(tmp)
def read_xml():
    fi=os.lstat(SERVER_XML)
    if stat.S_ISLNK(fi.st_mode) or not stat.S_ISREG(fi.st_mode) or fi.st_size>4<<20:raise RuntimeError("unsafe Tomcat server.xml")
    parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True));tree=ET.parse(SERVER_XML,parser=parser);return tree
def http_connectors(root):
    out=[]
    for elem in root.iter("Connector"):
        protocol=(elem.attrib.get("protocol") or "").upper()
        if "port" in elem.attrib and (not protocol or "HTTP" in protocol):out.append(elem)
    return out
def hosts(root):return list(root.iter("Host"))
def backup_path(service_id: str)->str:return os.path.join(STATE_ROOT,"tomcat-"+service_id+"-original.json")
def load_backup(path: str):
    fi=os.lstat(path)
    if stat.S_ISLNK(fi.st_mode) or not stat.S_ISREG(fi.st_mode) or fi.st_size>64<<10:raise RuntimeError("unsafe Tomcat backup record")
    with open(path,"r",encoding="utf-8") as f:return json.load(f)
def main():
    module=AnsibleModule(argument_spec=dict(service_id=dict(type="str",required=True),address=dict(type="str",required=True),port=dict(type="int",required=True),app_base=dict(type="str",default=""),state=dict(type="str",choices=["present","absent"],default="present")),supports_check_mode=False)
    try:
        sid=module.params["service_id"];address=module.params["address"];port=module.params["port"];app_base=module.params["app_base"];state=module.params["state"]
        if not UUID_RE.fullmatch(sid):raise ValueError("invalid service UUID")
        ipaddress.ip_address(address)
        if port<1 or port>65535:raise ValueError("invalid Tomcat listener port")
        if app_base and (not SAFE_PATH_RE.fullmatch(app_base) or not os.path.isabs(app_base) or os.path.normpath(app_base)!=app_base):raise ValueError("unsafe Tomcat appBase")
        tree=read_xml();root=tree.getroot();connectors=http_connectors(root)
        if len(connectors)!=1:raise RuntimeError("exactly one Tomcat HTTP Connector is required")
        connector=connectors[0];host_list=hosts(root)
        if app_base and len(host_list)!=1:raise RuntimeError("exactly one Tomcat Host is required for appBase management")
        bpath=backup_path(sid);changed=False
        if state=="present":
            if not os.path.exists(bpath):
                record={"connector":{"port":connector.attrib.get("port",""),"address":connector.attrib.get("address",""),"had_address":"address" in connector.attrib},"host":None}
                if app_base:
                    host=host_list[0];record["host"]={"app_base":host.attrib.get("appBase",""),"had_app_base":"appBase" in host.attrib}
                atomic_write(bpath,(json.dumps(record,sort_keys=True,indent=2)+"\n").encode("utf-8"),0o600)
            if connector.attrib.get("port")!=str(port):connector.set("port",str(port));changed=True
            if connector.attrib.get("address")!=address:connector.set("address",address);changed=True
            if app_base:
                host=host_list[0]
                if host.attrib.get("appBase")!=app_base:host.set("appBase",app_base);changed=True
        else:
            if os.path.exists(bpath):
                record=load_backup(bpath);cb=record.get("connector") or {};original_port=cb.get("port")
                if not original_port:raise RuntimeError("invalid Tomcat connector backup")
                if connector.attrib.get("port")!=original_port:connector.set("port",original_port);changed=True
                if cb.get("had_address"):
                    if connector.attrib.get("address")!=cb.get("address",""):connector.set("address",cb.get("address",""));changed=True
                elif "address" in connector.attrib:del connector.attrib["address"];changed=True
                hb=record.get("host")
                if hb is not None:
                    if len(host_list)!=1:raise RuntimeError("Tomcat Host topology changed; refusing ambiguous restore")
                    host=host_list[0]
                    if hb.get("had_app_base"):
                        if host.attrib.get("appBase")!=hb.get("app_base",""):host.set("appBase",hb.get("app_base",""));changed=True
                    elif "appBase" in host.attrib:del host.attrib["appBase"];changed=True
                os.remove(bpath)
        if changed:
            ET.indent(tree,space="  ");payload=ET.tostring(root,encoding="utf-8",xml_declaration=True);atomic_write(SERVER_XML,payload+b"\n",0o644)
            read_xml()
        module.exit_json(changed=changed)
    except (OSError,ValueError,RuntimeError,ET.ParseError,json.JSONDecodeError) as exc:module.fail_json(msg=str(exc))
if __name__=="__main__":main()
