import os, sys, time, argparse
from pprint import pprint
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeAuthSSHKey

sys.path.insert(0, os.environ['HOME']+"/.rexec")
try:
    import config
except:
    config = None

g_driver = None

#
# for now providers are EC2 or GCE
#
def init(access=None, secret=None, region=None, project=None, provider="EC2"):
    global g_driver, g_access, g_secret, g_region
    cls = get_driver(Provider[provider])
    if access==None:
        if config==None:
            raise Exception("no config file or parameters")
        g_access = config.access
        g_secret = config.secret
        g_region = config.region
    else:
        g_access = access
        g_secret = secret
        g_region = region
    if provider == 'EC2':
        g_driver = cls(g_access, g_secret, region=g_region)
    elif provider == 'GCE':
        if project == None and provider == "GCE":
            project = config.project
        g_driver = cls(g_access, g_secret, datacenter=g_region, project=project)
    else:
        print ("ERROR: unknown cloud provider", provider)

def get_credentials():
    return g_access, g_secret, g_region

def get_server(url=None, uuid=None, name=None, access=None, secret=None, region=None):
    if g_driver == None:
        init(access, secret, region)
    nodes = g_driver.list_nodes()
    if url:
        node = [x for x in nodes if url in x.public_ips and x.state != 'terminated']
    elif uuid:
        node = [x for x in nodes if x.uuid.find(uuid)==0 and x.state != 'terminated']
    elif name:
        node = [x for x in nodes if x.name==name and x.state != 'terminated']
    else:
        return "error: specify url, uuid, or name"
    return node[0] if node else None

def get_server_state(srv):
    return g_driver.list_nodes(ex_node_ids=[srv.id])[0].state

def start_server(srv):
    result = srv.start()
    if not result:
        return "error starting server"
    state = None
    while state != 'running':
        state = get_server_state(srv)
        time.sleep(2)
        print ("server state:", state)
    print ("Waiting for public IP address to be assigned")
    g_driver.wait_until_running([srv])
    while len(srv.public_ips)==0:
        srv = g_driver.list_nodes(ex_node_ids=[srv.id])[0]
        print("Public IP's:", srv.public_ips)
        time.sleep(5)
    return srv

#FIXME: AWS specific
def launch_server(name, size=None, image=None, pubkey=None, access=None, secret=None, region=None):
    if g_driver == None:
        init(access, secret, region)
    # if image==None:
    #     # image = "ami-003634241a8fcdec0"
    #     image = "ami-0ba3ac9cd67195659"
    images = g_driver.list_images(ex_image_ids=[image])
    if not images:
        raise Exception("Image %s not found" % image)
    image = images[0]

    # if size==None:
    #     size = "t2.small"
    sizes = [x for x in g_driver.list_sizes() if x.name == size]
    if not sizes:
        raise Exception("Instance size %s not found" % size)
    size = sizes[0]

    print ("Launching instance node, image=%s, name=%s, size=%s" % (image.id, name, size.id))
    if pubkey:
        auth = NodeAuthSSHKey(pubkey)
        node = g_driver.create_node(name, size, image, auth=auth)
    else:
        node = g_driver.create_node(name, size, image)
    print ("Waiting for public IP address to be active")
    g_driver.wait_until_running([node])
    while len(node.public_ips)==0:
        node = g_driver.list_nodes(ex_node_ids=[node.id])[0] #refresh node -- is this really necessary
        print("Public IP's:", node.public_ips)
        time.sleep(5)
    return node

def stop_server(srv):
    result = srv.stop_node()
    if not result:
        return "error stopping server"
    state = None
    while state != 'stopped':
        state = get_server_state(srv)
        time.sleep(2)
        print ("server state:", state)
    return "success"

def terminate_server(srv):
    result = g_driver.destroy_node(srv)
    if not result:
        return "error terminating server"
    state = None
    while state != 'terminated':
        state = get_server_state(srv)
        time.sleep(2)
        print ("server state:", state)
    return "success"

def list_servers(name, access=None, secret=None, region=None):
    if g_driver == None:
        init(access, secret, region)
    nodes = g_driver.list_nodes()
    nodes = [x for x in nodes if x.name==name]
    return nodes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--uuid")
    parser.add_argument("--name")
    args, unknown = parser.parse_known_args()

    n = get_server(args.url, args.uuid, args.name)
    pprint (n)