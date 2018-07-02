# 量化交易赚取手续费

    ## 目前支持以下交易所
        FCoin

    ## 安装运行
        需要python3支持

    pip install requests

    -bs 基础兑换货币 例如 usdt btc
    -s 交易的symbol 例如 ft xrp etc btc
    -f 手续费 每个币种不一样
    -p 获利价
    -m 持有的最小可卖数量
    -r 每次买 账户比例 0.2 每次账户的20%
    nohup python main.py -s etc -f 0.0001 -p 0.0001 -m 0.0001 >> /tmp/etc &





