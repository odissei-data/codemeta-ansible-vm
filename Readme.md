# Bridging the Metadata Gap: Automated VRE Provisioning via Agentic AI and CodeMeta Knowledge Graphs

## Abstract
Virtual Research Environments (VREs) are essential for modern data-driven research, yet the manual overhead of configuring these environments remains a significant barrier for researchers in the Social Sciences and Humanities (SSH). This paper proposes a framework within the Macroscope project to automate VRE setup by leveraging Agentic AI for metadata generation. By populating a Knowledge Graph with CodeMeta descriptions generated automatically from software repositories, we enable a machine-readable pipeline that bridges the gap between raw data access and functional, containerized research environments.

<img width="1354" height="792" alt="image" src="https://github.com/user-attachments/assets/68db96af-450c-4a53-9e5b-a796d0f04cb2" />

## Question we try to solve:
- Which tools and versions can manipulate my specific data?
- Are the software licenses compatible with my research stack and institutional requirements?
- What are the specific operating system, memory, and CPU requirements?
- Where is the documentation, and how should packages be sequenced during installation?
- Is there a citable publication or an ORCID associated with the authors?

## SSHOC-NL project aim:
- Automatic configuration of SANE VMs using information from the Knowledge Graph.

# How to run

Install Multipass to create your VMs locally (Experiments with Macbook):
- `brew install --cask multipass`

Install PyYAML and requests: You'll need this for the Python script to read your configuration. 
- `pip install pyyaml`
- `pip install requests`

Execution
- `python extrac_run.py`

# Ansible script experiments
**extrac_run.py** creates a ansible script **deploy.yml** file and runs a VM configured by it.

One of the ideas is to use this ansible script file to create a vm in other environments; there's no need to be multipass on a MacBook or another operational system.

# How it Works
The script leverages macOS's Hypervisor via Multipass. Here is a high-level look at how the layers interact:
- **YAML Parsing**: The script uses PyYAML to turn your human-readable settings into a Python dictionary.
- **Resource Allocation**: It maps the CPUs, memory, and disk keys directly to the command-line arguments that Multipass requires.
- **Cloud-Init**: If you want the VM to come pre-installed with software (like Git or Docker), the cloud_init section handles that automatically upon the first boot.
- **Native Performance**: Because it uses the Virtualization Framework (on Apple Silicon or Intel), there is very little overhead compared to heavier tools like VirtualBox.

## Useful Management VM multipass Commands
Once your script has started the VM, you can manage it from your terminal. Here are some useful commands:
- **Enter the VM**	`multipass shell build-box`
- **Check Status**	`multipass list`
- **Stop the VM**	`multipass stop build-box`
- **Delete the VM** `multipass delete --purge build-box`


