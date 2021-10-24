"""An example of constructing a profile with a single Xen VM.

Instructions:
Wait for the profile instance to start, and then log in to the VM via the
ssh port specified below.  (Note that in this case, you will need to access
the VM through a high port on the physical host, since we have not requested
a public IP address for the VM itself.)
"""

# Import the Portal object.
import geni.portal as portal
# Import the ProtoGENI library.
import geni.rspec.pg as pg

# Create the Portal context.
pc = portal.Context()
 
# Create a Request object to start building the RSpec.
rspec = pg.Request()
 
# Create a XenVM and add it to the RSpec.
node = pg.XenVM("node")
rspec.addResource(node)

# Print the RSpec to the enclosing page.
pc.printRequestRSpec(rspec)
