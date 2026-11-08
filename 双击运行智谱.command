#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ -x .venv/bin/python ]]; then
    .venv/bin/python run_zhipu.py
    result=$?
else
    print '项目缺少 .venv，请先配置 Python 环境。'
    result=1
fi
read -r '?按回车关闭窗口…'
exit $result
