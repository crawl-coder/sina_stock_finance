# -*- coding: UTF-8 -*-
"""
sina_stock_finance 数据项定义
"""

from crawlo.items import Item, Field


class SinaStockFinanceItem(Item):
    """新浪财经研究报告数据项"""

    # ---- 列表页字段 ----
    title = Field(desc="研报标题", nullable=False)
    url = Field(desc="研报详情页地址")
    report_type = Field(desc="报告类型（宏观/行业/公司/策略/债券/基金/晨报等）")
    pub_date = Field(desc="发布日期")
    org_name = Field(desc="研究机构名称")
    researchers = Field(desc="研究员（多人用/分隔）", default="")

    # ---- 详情页字段 ----
    content = Field(desc="研报正文内容", default="")
