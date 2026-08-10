# -*- coding: UTF-8 -*-
"""
爬虫：stock_finance
采集新浪财经最新滚动研究报告。

列表页: https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/lastest/index.phtml
详情页: https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/lastest/rptid/{rptid}/index.phtml
"""

import re
import os

from crawlo.spider import Spider
from crawlo import Request, Response
from ..items import SinaStockFinanceItem


class StockFinanceSpider(Spider):
    """新浪财经研究报告爬虫"""

    name = 'stock_finance'
    allowed_domains = ['stock.finance.sina.com.cn']

    # 列表页基础 URL
    BASE_URL = 'https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/lastest/index.phtml'

    # 请求头
    DEFAULT_HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/lastest/index.phtml",
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    }

    # Cookies
    DEFAULT_COOKIES = {
        "UOR": ",,",
        "SINAGLOBAL": "113.84.33.237_1767254023.168112",
        "FINA_V_S_2": "sh600118",
        "SCF": "Aqttn8OBAMwF_ym6d98Ukso_CiJQjLchSZyZwyrzrmjvhs_on7R3J8NLMn6fz3jbZQ5UWRZgt_h3XLWqG9QuZm0.",
        "Hm_lvt_90c40f528e0b2106bc03da5aadec190f": "1785907155",
        "Apache": "223.104.86.108_1786349530.679146",
        "SFA_version10.8.0": "2026-08-10%2016%3A09",
        "SFA_version10.8.0_click": "1",
        "SUB": "_2A25HffeNDeRhGeFJ4lcV8y_JzzuIHXVk83VFrDV_PUNbm9B-LVmhkW9NfqFqPwHFEHKsiXEULcRITmuIAlRT1QaK",
        "SUBP": "0033WrSXqPxfM725Ws9jqgMF55529P9D9Wh9BBHfK4A2iwCYYl7jorR45NHD95QNS0.fShepSKBNWs4Dqcj_i--Xi-isi-2pi--Xi-iFi-z7i--4i-i8iK.4i--fi-2Xi-zXi--RiKnEi-2p",
        "ALF": "1788941533",
        "hqEtagMode": "1",
        "ULV": "1786349535731:10:1:1:223.104.86.108_1786349530.679146:1784903321926",
        "U_TRS1": "0000006c.c6a626a.6a7987e1.cb0f077c",
        "U_TRS2": "0000006c.c6b026a.6a7987e1.9c828342",
        "rotatecount": "4",
        "SR_SEL": "1_511",
    }

    # 最大爬取页数（None = 不限）；可用环境变量 STOCK_MAX_PAGES 覆盖（冒烟/分布式限制）
    MAX_PAGES = int(os.environ.get('STOCK_MAX_PAGES', '212'))

    custom_settings = {
        'concurrency': 8,
        'download_delay': 1.0,
    }

    def start_requests(self):
        """生成初始请求 — 一次性推送全部列表页（1..MAX_PAGES）。

        分布式场景下必须批量入队：5 个 Worker 并行消费各列表页，
        而不是串行翻页（parse 内 yield 下一页会形成串行链，
        翻页间隙易触发 idle 退出、限制并行度）。
        种子锁保证只有 Leader 生成这些请求。
        """
        max_pages = self.MAX_PAGES or 1
        for page in range(1, max_pages + 1):
            yield Request(
                url=self.BASE_URL,
                params={'p': str(page)},
                headers=self.DEFAULT_HEADERS,
                cookies=self.DEFAULT_COOKIES,
                callback=self.parse,
                meta={'page': page},
            )

    def parse(self, response: Response):
        """解析列表页，提取研究报告摘要数据，生成详情页请求。

        所有列表页已在 start_requests 一次性入队，这里不再翻页。
        """
        self.logger.info(f'正在解析列表页: 第 {response.meta["page"]} 页, URL: {response.url}')

        rows = response.css('table.tb_01 tr')
        item_count = 0

        for row in rows:
            tds = row.css('td')
            if len(tds) < 6:
                continue

            seq_text = tds[0].css('::text').get(default='').strip()
            if not seq_text.isdigit():
                continue

            # ---- 列表页字段 ----
            title_link = tds[1].css('a')
            title = title_link.css('::text').get(default='').strip()
            detail_url = title_link.css('::attr(href)').get(default='').strip()
            if detail_url.startswith('//'):
                detail_url = 'https:' + detail_url

            report_type = tds[2].css('::text').get(default='').strip()
            pub_date = tds[3].css('::text').get(default='').strip()

            org_name = tds[4].css('div.fname05 span::text').get(default='').strip()
            if not org_name:
                org_name = tds[4].css('::text').get(default='').strip()

            researchers = tds[5].css('div.fname span::text').get(default='').strip()
            if not researchers:
                researchers = tds[5].css('::text').get(default='').strip()

            item_count += 1

            # 发起详情页请求，通过 meta 传递列表页已解析的字段
            yield Request(
                url=detail_url,
                headers=self.DEFAULT_HEADERS,
                cookies=self.DEFAULT_COOKIES,
                callback=self.parse_detail,
                meta={
                    'title': title,
                    'url': detail_url,
                    'report_type': report_type,
                    'pub_date': pub_date,
                    'org_name': org_name,
                    'researchers': researchers,
                },
            )

        self.logger.info(f'第 {response.meta["page"]} 页解析完成，提取 {item_count} 条数据')

    def parse_detail(self, response: Response):
        """
        解析详情页，提取研报正文内容。

        详情页结构（参考 content.html）:
        <div class="main clearfix">
            <div class="ml">
                <div class="blk_02">
                    <div class="content">
                        <h1>研报标题</h1>
                        <div class="creab">
                            <span>类别：宏观</span>
                            <span>机构：...</span>
                            <span>研究员：...</span>
                            <span>日期：2026-08-10</span>
                        </div>
                        <div class="blk_container">
                            <p>正文内容...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        # 从 meta 中获取列表页已解析的字段
        meta = response.meta

        # 提取正文内容（.blk_container 下的所有 p 标签文本）
        content_parts = response.css('div.blk_container p::text').getall()
        content = '\n'.join(part.strip() for part in content_parts if part.strip())

        yield SinaStockFinanceItem(
            title=meta['title'],
            url=meta['url'],
            report_type=meta['report_type'],
            pub_date=meta['pub_date'],
            org_name=meta['org_name'],
            researchers=meta['researchers'],
            content=content,
        )


