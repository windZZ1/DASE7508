"""Replace the saved Zhipu API key from the VS Code play button."""
from travel_agent.configure import main


if __name__ == '__main__':
    main(['--provider', 'zhipu'])
    print('密钥已更新。打开 run_zhipu.py，点击 ▶ 运行。')
