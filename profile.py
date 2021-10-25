"""An example of constructing a profile with a single raw PC. It can be instantiated on any cluster; the node will boot the default operating system, which is typically a recent version of Ubuntu.

Instructions:
Wait for the profile instance to start, then click on the node in the topology and choose the `shell` menu item. 
"""

# Import the Portal object.
import geni.portal as portal
# Import the ProtoGENI library.
import geni.rspec.pg as RSpec
import geni.urn as urn
import geni.aggregate.cloudlab as cloudlab

# Create a portal context.
pc = portal.Context()

images = [ ("UBUNTU16-64-STD", "Ubuntu 16.04"),
           ("UBUNTU14-64-STD", "Ubuntu 14.04")]
           
types  = [ ("m510", "m510 (Intel Xeon-D)"),
           ("m400", "m400 (ARM - APM X-Gene)")]
           
pc.defineParameter("image", "Disk Image",
                   portal.ParameterType.IMAGE, images[0], images)
                   
pc.defineParameter("type", "Node Type",
                   portal.ParameterType.NODETYPE, types[0], types)

params = pc.bindParameters()

# Create a Request object to start building the RSpec.
rspec = RSpec.Request()
 
# Add a raw PC to the request.
node = RSpec.RawPC("node")
node.hardware_type = params.type
node.disk_image = urn.Image(cloudlab.Utah,"emulab-ops:%s" % params.image)
rspec.addResource(node)

# Print the RSpec to the enclosing page.
pc.printRequestRSpec(rspec)
