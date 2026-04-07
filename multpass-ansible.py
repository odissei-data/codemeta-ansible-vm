import subprocess
import requests
import sys
import os
import time

def run_command(command, description):
    print(f"==> {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Erro: {e.stderr}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 setup_multipass_ansible.py <URL_DO_YAML>")
        sys.exit(1)

    yaml_url = sys.argv[1]
    vm_name = "odissei-vm"
    local_yaml = "deploy_temp.yml"

    # 1. Baixar o script Ansible
    print(f"==> Baixando script de: {yaml_url}")
    response = requests.get(yaml_url)
    if response.status_code != 200:
        print("Erro ao baixar o arquivo YAML.")
        sys.exit(1)
    
    # 2. Filtrar o YAML (Remover blocos de Cleanup para o serviço persistir)
    content = response.text
    # Separamos os plays pelo marcador '---' e ignoramos os que contêm "Cleanup"
    plays = content.split('---')
    filtered_plays = [p for p in plays if "Cleanup" not in p]
    
    with open(local_yaml, "w") as f:
        f.write("---\n".join(filtered_plays))

    # 3. Criar a VM Multipass
    run_command(f"multipass launch --name {vm_name} --cpus 2 --memory 4G", "Criando VM Multipass")

    # 4. Obter IP da VM
    vm_ip = run_command(f"multipass info {vm_name} --format csv", "Obtendo IP").splitlines()[1].split(',')[2]
    print(f"==> VM IP: {vm_ip}")

    # 5. Configurar SSH (Gera chave se não existir e envia para a VM)
    if not os.path.exists(os.path.expanduser("~/.ssh/id_rsa")):
        run_command("ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''", "Gerando chave SSH")
    
    pub_key = open(os.path.expanduser("~/.ssh/id_rsa.pub")).read().strip()
    run_command(f"multipass exec {vm_name} -- bash -c 'mkdir -p ~/.ssh && echo \"{pub_key}\" >> ~/.ssh/authorized_keys'", "Configurando acesso SSH")

    # 6. Instalar Ansible no Host (caso não tenha)
    run_command("brew install ansible", "Garantindo que Ansible está instalado")

    # 7. Criar Inventário Temporário
    inventory = f"[all]\n{vm_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa ansible_ssh_extra_args='-o StrictHostKeyChecking=no'"
    with open("hosts_temp.ini", "w") as f:
        f.write(inventory)

    # 8. Executar o Ansible
    print("==> Executando Ansible Playbook...")
    # Nota: O seu script original usa templates locais. 
    # Se eles não existirem na pasta, a tarefa de cópia falhará.
    os.system(f"ansible-playbook -i hosts_temp.ini {local_yaml}")

    print(f"\n✅ Concluído! Acesse o serviço em: http://{vm_ip}:8080")

if __name__ == "__main__":
    main()