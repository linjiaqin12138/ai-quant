from datetime import datetime, timedelta
from typing import List
import pytest

from lib.utils.time import dt_to_ts, ts_to_dt
from lib.adapter.database.news_cache import NewsInfo
from lib.adapter.database import create_transaction
from lib.modules.news_proxy import NewsFetchProxy

from fake_modules.fake_news import fakenews

fake_news_list_of_cointime = [
    NewsInfo(
        news_id="566099",
        title='DWF Labs推出2000万美元"Meme基金"',
        timestamp=datetime(2024, 11, 20, 19, 35, 17),
        url="/flash-news/dwf-labs-tui-chu-2000-wan-mei-yuan-meme-ji-jin-94231",
        platform="cointime",
        description='DWF Labs宣布推出2000万美元的"Meme基金"，以支持多个区块链上的创新Meme币项目。"Meme基金"现在正接受寻求投资和指导的Meme币项目的提案。',
    ),
    NewsInfo(
        news_id="566108",
        title="UNI突破9美元",
        timestamp=datetime(2024, 11, 20, 19, 43, 28),
        url="/flash-news/uni-tu-po-9-mei-yuan-91474",
        platform="cointime",
        description="行情显示，UNI突破9美元，现报9.01美元，24小时跌幅达到5.56%，行情波动较大，请做好风险控制。",
    ),
    NewsInfo(
        news_id="566116",
        title="不丹王国所拥有比特币的价值已占其 GDP 的 34%",
        timestamp=datetime(2024, 11, 20, 19, 57, 2),
        url="/flash-news/bu-dan-wang-guo-suo-yong-you-bi-te-bi-de-jia-zhi-yi-zhan-qi-gdp-de-34-85095",
        platform="cointime",
        description="据 Arkham 数据，不丹王国地址持有的比特币价值已达到 11 亿美元，占其 GDP 的 34%。",
    ),
    NewsInfo(
        news_id="566135",
        title="Acurx Pharmaceuticals董事会批准购买100万美元的比特币作为储备资产",
        timestamp=datetime(2024, 11, 20, 20, 16, 55),
        url="/flash-news/acurx-pharmaceuticals-dong-shi-hui-pi-zhun-gou-mai-100-wan-mei-yuan-de-bi-te-bi-zuo-wei-chu-bei-zi-chan-89",
        platform="cointime",
        description="和2023年同季度的3,332万美元相比增长显著。总收入包括产品收入6,458万美元、挖矿收入896万美元和其他收入6.5万美元。挖矿收入：2024年第三季度挖矿收入为896万美元，与2024年第二季度的931万美元基本持平，较2023年同季度的326万美元增长显著。同比增长主要因为挖矿算力的增加。截至2024年9月30日，公司共持有1,231.3枚比特币，持有加密货币资产和加密货币应收款的公允价值合计为7,902万美元。",
    ),
    NewsInfo(
        news_id="566147",
        title="调查：106位分析师中有94位认为美联储12月将降息25个基点",
        timestamp=datetime(2024, 11, 20, 20, 24, 5),
        url="/flash-news/diao-cha-106-wei-fen-xi-shi-zhong-you-94-wei-ren-wei-mei-lian-chu-12-yue-jiang-jiang-xi-25-ge-ji-dian-60797",
        platform="cointime",
        description="路透调查：106位分析师中有94位认为美联储12月将降息25个基点至4.25%-4.50%。",
    ),
]

fake_news_proxy = NewsFetchProxy(news_fetcher=fakenews)


def test_hot_news_cache_ok():
    fakenews.set_news(
        "qq-news",
        [
            NewsInfo(
                **{
                    "news_id": "20241120A05TOG00",
                    "title": "微软困在Copilot里：员工称造假神、集体幻觉，客户骂没用、不安全",
                    "timestamp": ts_to_dt(1732087114000),
                    "url": "https://new.qq.com/rain/a/20241120A05TOG00",
                    "platform": "qq-news",
                }
            ),
            NewsInfo(
                **{
                    "news_id": "20241120A06EBR00",
                    "title": "国家烟草专卖局原党组成员、副局长被“双开",
                    "timestamp": ts_to_dt(1732089600000),
                    "url": "https://view.inews.qq.com/k/20241120A06EBR00",
                    "platform": "qq-news",
                }
            ),
            NewsInfo(
                **{
                    "news_id": "20241120A04UNY00",
                    "title": "“浙江烧伤妈妈”丈夫已开橱窗带货，目前上架577件商品",
                    "description": "近日，在浙江诸暨，37岁女子遭遇煤气爆炸后忍痛抱回儿子，引发网友关注。11月19日，“浙江烧伤妈妈”丈夫许先生（@奇梅异卉之诺） 发布妻子康复动态，记者注意到其在社交平台上已开橱窗带货，目前上架了577件商品。图源：当事人社交账号此前，“烧伤妈妈”因遭遇煤气爆炸后忍痛抱回儿子，引发网友关注。遭遇爆燃事故之后，...",
                    "timestamp": ts_to_dt(1732080714000),
                    "url": "https://view.inews.qq.com/k/20241120A04UNY00",
                    "platform": "qq-news",
                }
            ),
        ],
    )

    hot_news = fake_news_proxy.get_current_hot_news("qq-news")
    assert len(hot_news) == 3
    assert hot_news[0].news_id == "20241120A05TOG00"
    assert hot_news[-1].news_id == "20241120A04UNY00"
    with create_transaction() as db:
        cache_record = db.kv_store.get(
            'cache:lib.modules.news_proxy||NewsFetchProxy.get_current_hot_news||platform="qq-news"'
        )
        assert cache_record != None and datetime.now() - datetime.fromisoformat(
            cache_record["expire_time"]
        ) < timedelta(minutes=5)

    # 用了缓存没有调用接口
    fakenews.set_news("qq-news", [])
    hot_news = fake_news_proxy.get_current_hot_news("qq-news")
    assert len(hot_news) == 3
    assert hot_news[0].news_id == "20241120A05TOG00"
    assert hot_news[-1].news_id == "20241120A04UNY00"


def test_get_news_during_with_cache():
    fake_news_list = [
        NewsInfo(
            news_id="566099",
            title='DWF Labs推出2000万美元"Meme基金"',
            timestamp=datetime(2024, 11, 20, 19, 35, 17),
            url="/flash-news/dwf-labs-tui-chu-2000-wan-mei-yuan-meme-ji-jin-94231",
            platform="cointime",
            description='DWF Labs宣布推出2000万美元的"Meme基金"，以支持多个区块链上的创新Meme币项目。"Meme基金"现在正接受寻求投资和指导的Meme币项目的提案。',
        ),
        NewsInfo(
            news_id="566108",
            title="UNI突破9美元",
            timestamp=datetime(2024, 11, 20, 19, 43, 28),
            url="/flash-news/uni-tu-po-9-mei-yuan-91474",
            platform="cointime",
            description="行情显示，UNI突破9美元，现报9.01美元，24小时跌幅达到5.56%，行情波动较大，请做好风险控制。",
        ),
        NewsInfo(
            news_id="566116",
            title="不丹王国所拥有比特币的价值已占其 GDP 的 34%",
            timestamp=datetime(2024, 11, 20, 19, 57, 2),
            url="/flash-news/bu-dan-wang-guo-suo-yong-you-bi-te-bi-de-jia-zhi-yi-zhan-qi-gdp-de-34-85095",
            platform="cointime",
            description="据 Arkham 数据，不丹王国地址持有的比特币价值已达到 11 亿美元，占其 GDP 的 34%。",
        ),
        NewsInfo(
            news_id="566135",
            title="Acurx Pharmaceuticals董事会批准购买100万美元的比特币作为储备资产",
            timestamp=datetime(2024, 11, 20, 20, 16, 55),
            url="/flash-news/acurx-pharmaceuticals-dong-shi-hui-pi-zhun-gou-mai-100-wan-mei-yuan-de-bi-te-bi-zuo-wei-chu-bei-zi-chan-89",
            platform="cointime",
            description="和2023年同季度的3,332万美元相比增长显著。总收入包括产品收入6,458万美元、挖矿收入896万美元和其他收入6.5万美元。挖矿收入：2024年第三季度挖矿收入为896万美元，与2024年第二季度的931万美元基本持平，较2023年同季度的326万美元增长显著。同比增长主要因为挖矿算力的增加。截至2024年9月30日，公司共持有1,231.3枚比特币，持有加密货币资产和加密货币应收款的公允价值合计为7,902万美元。",
        ),
        NewsInfo(
            news_id="566147",
            title="调查：106位分析师中有94位认为美联储12月将降息25个基点",
            timestamp=datetime(2024, 11, 20, 20, 24, 5),
            url="/flash-news/diao-cha-106-wei-fen-xi-shi-zhong-you-94-wei-ren-wei-mei-lian-chu-12-yue-jiang-jiang-xi-25-ge-ji-dian-60797",
            platform="cointime",
            description="路透调查：106位分析师中有94位认为美联储12月将降息25个基点至4.25%-4.50%。",
        ),
    ]
    # Case1: 初始化本地cointime新闻缓存
    fakenews.set_news("cointime", fake_news_list)

    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 11, 20, 19, 43, 28),
        end=datetime(2024, 11, 20, 19, 57, 2),
    )
    assert len(cointime_news) == 1  # 位于end的566116不会被查到
    assert cointime_news[0].news_id == "566108"

    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 1
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert (
            local_time_range_context["start"]
            == (local_time_range_context["end"] - 1)
            == dt_to_ts(datetime(2024, 11, 20, 19, 43, 28))
        )

    # Case2: 本地cointime新闻缓存覆盖前一部分范围
    fakenews.set_news(
        "cointime", fake_news_list[2:4]
    )  # remove the cache news and will not be returned
    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 11, 20, 19, 43, 28),
        end=datetime(2024, 11, 20, 20, 16, 56),
    )
    assert len(cointime_news) == 3
    assert cointime_news[0].news_id == "566108"

    with create_transaction() as db:
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        assert len(db.session.execute("select * from hot_news_cache").rows) == 3

        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(
            fake_news_list[1].timestamp
        )
        assert (
            local_time_range_context["end"] == dt_to_ts(fake_news_list[3].timestamp) + 1
        )

    # Case3: 本地cointime新闻缓存覆盖整个范围
    fakenews.set_news("cointime", [])  # 不需要API返回
    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 11, 20, 19, 43, 28),
        end=datetime(2024, 11, 20, 20, 16, 55),
    )
    assert len(cointime_news) == 2

    # Case4: 本地cointime新闻缓存覆盖后一部分范围
    fakenews.set_news("cointime", fake_news_list)  # 不需要API返回
    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 11, 20, 19, 35, 17),
        end=datetime(2024, 11, 20, 20, 16, 55),
    )
    assert len(cointime_news) == 3
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 4
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(
            fake_news_list[0].timestamp
        )
        assert (
            local_time_range_context["end"] == dt_to_ts(fake_news_list[3].timestamp) + 1
        )

    # Case5: 本地cointime新闻缓存覆盖中间一部分范围
    earlier_news = NewsInfo(
        news_id="567756",
        title="USDT的日交易量几乎是比特币的两倍，且是以太坊的四倍",
        timestamp=datetime(2024, 11, 20, 10, 00, 00),
        url="https://cn.cointime.ai/flash-news/usdt-de-ri-jiao-yi-liang-ji-hu-shi-bi-te-bi-de-liang-bei-qie-shi-yi-tai-fang-de-si-bei-17850",
        platform="cointime",
        description="据X用户Rocelo Lopes分享的数据，USDT的日交易量几乎是比特币的两倍，且是以太坊的四倍。Tether首席执行官Paolo Ardoino转发了该推文。",
    )
    fakenews.set_news("cointime", [earlier_news] + fake_news_list)
    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 11, 20, 9, 1, 1),
        end=datetime(2024, 11, 20, 21, 0, 0),
    )
    assert len(cointime_news) == 6
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 6
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(earlier_news.timestamp)
        assert (
            local_time_range_context["end"]
            == dt_to_ts(fake_news_list[-1].timestamp) + 1
        )

    # Case6: 本地cointime新闻缓存没有覆盖
    latest_news = NewsInfo(
        news_id="xxxxxx",
        title="USDT的日交易量几乎是比特币的两倍，且是以太坊的四倍",
        timestamp=datetime(2024, 11, 21, 20, 24, 5),
        url="https://cn.cointime.ai/flash-news/usdt-de-ri-jiao-yi-liang-ji-hu-shi-bi-te-bi-de-liang-bei-qie-shi-yi-tai-fang-de-si-bei-17850",
        platform="cointime",
        description="据X用户Rocelo Lopes分享的数据，USDT的日交易量几乎是比特币的两倍，且是以太坊的四倍。Tether首席执行官Paolo Ardoino转发了该推文。",
    )
    fakenews.set_news("cointime", fake_news_list + [latest_news])
    cointime_news = fake_news_proxy.get_news_during(
        "cointime",
        start=datetime(2024, 12, 1, 0, 0, 0),
        end=datetime(2024, 12, 2, 0, 0, 0),
    )
    assert len(cointime_news) == 0
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 7
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(earlier_news.timestamp)
        assert local_time_range_context["end"] == dt_to_ts(latest_news.timestamp) + 1

    # Clean up
    with create_transaction() as db:
        db.session.execute("delete from hot_news_cache")
        db.session.execute(
            "delete from events where `key`='cointime_news_cache_time_range'"
        )
        db.commit()


@pytest.mark.skip(reason="Sqlite模式下不支持并发测试")
def test_get_news_parallelly_with_only_one_api_call():
    fakenews.set_news("cointime", fake_news_list_of_cointime)

    def query_func():
        try:
            fake_fetch_proxy = NewsFetchProxy(news_fetcher=fakenews)
            cointime_news = fake_fetch_proxy.get_news_during(
                "cointime",
                fake_news_list_of_cointime[0].timestamp,
                fake_news_list_of_cointime[-1].timestamp + timedelta(seconds=1),
            )
            if len(cointime_news) == len(fake_news_list_of_cointime):
                return
        except Exception as err:
            print(err)

    import threading

    threads: List[threading.Thread] = []
    for _ in range(4):
        threads.append(threading.Thread(target=query_func))

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    with create_transaction() as db:
        db.session.execute("delete from hot_news_cache")
        db.session.execute(
            "delete from events where `key`='cointime_news_cache_time_range'"
        )
        db.commit()

    assert fakenews.get_call_times("get_news_during") == 1


def test_get_news_from_with_cache():
    # Case 1: init cointime cache
    fakenews.set_news("cointime", [fake_news_list_of_cointime[2]])
    cointime_news = fake_news_proxy.get_news_from(
        "cointime", fake_news_list_of_cointime[2].timestamp
    )
    assert len(cointime_news) == 1
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 1
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert (
            local_time_range_context["start"]
            == (local_time_range_context["end"] - 1)
            == dt_to_ts(fake_news_list_of_cointime[2].timestamp)
        )

    # Case 2: 缓存覆盖前面一部分
    fakenews.set_news("cointime", fake_news_list_of_cointime[3:4])
    cointime_news = fake_news_proxy.get_news_from(
        "cointime", fake_news_list_of_cointime[2].timestamp
    )
    assert len(cointime_news) == 2
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 2
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(
            fake_news_list_of_cointime[2].timestamp
        )
        assert (
            local_time_range_context["end"]
            == dt_to_ts(fake_news_list_of_cointime[3].timestamp) + 1
        )

    # Case 3: 缓存没有覆盖到查询范围，从缓存缺失的地方开始查
    fakenews.set_news("cointime", fake_news_list_of_cointime[4:])
    with create_transaction() as db:
        db.kv_store.set(
            "cointime_news_cache_time_range",
            {
                "query_start": 1732103822000,
                "query_end": 1732105445010,
                "start": 1732103822000,
                "end": 1732105445000,
            },
        )
        db.session.commit()

    cointime_news = fake_news_proxy.get_news_from(
        "cointime", fake_news_list_of_cointime[4].timestamp + timedelta(seconds=1)
    )
    assert len(cointime_news) == 0
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 3
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(
            fake_news_list_of_cointime[2].timestamp
        )
        assert (
            local_time_range_context["end"]
            == dt_to_ts(fake_news_list_of_cointime[4].timestamp) + 1
        )

    # Case 4: 缓存没有覆盖一部分查询范围，缓存全部失效并全部用接口查询更新缓存
    fakenews.set_news("cointime", fake_news_list_of_cointime)
    cointime_news = fake_news_proxy.get_news_from(
        "cointime", fake_news_list_of_cointime[0].timestamp
    )
    assert len(cointime_news) == 5
    with create_transaction() as db:
        assert len(db.session.execute("select * from hot_news_cache").rows) == 5
        local_time_range_context = db.kv_store.get("cointime_news_cache_time_range")
        # 只有一条新闻，时间范围头尾相同
        assert local_time_range_context["start"] == dt_to_ts(
            fake_news_list_of_cointime[0].timestamp
        )
        assert (
            local_time_range_context["end"]
            == dt_to_ts(fake_news_list_of_cointime[-1].timestamp) + 1
        )

    with create_transaction() as db:
        db.session.execute("delete from hot_news_cache")
        db.session.execute(
            "delete from events where `key`='cointime_news_cache_time_range'"
        )
        db.session.commit()
