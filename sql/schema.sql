-- ============================================================
-- 新浪财经研究报告数据表
-- ============================================================

CREATE TABLE IF NOT EXISTS `sina_stock_finance` (
    `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    `title`        VARCHAR(512)    NOT NULL                COMMENT '研报标题',
    `url`          VARCHAR(768)    NOT NULL                COMMENT '研报详情页地址',
    `report_type`  VARCHAR(64)     NOT NULL DEFAULT ''     COMMENT '报告类型（宏观/行业/公司/策略/债券/基金/晨报等）',
    `pub_date`     DATE            NOT NULL                COMMENT '发布日期',
    `org_name`     VARCHAR(256)    NOT NULL DEFAULT ''     COMMENT '研究机构名称',
    `researchers`  VARCHAR(512)    NOT NULL DEFAULT ''     COMMENT '研究员（多人用/分隔）',
    `content`      MEDIUMTEXT                              COMMENT '研报正文内容',
    `created_at`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_url` (`url`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新浪财经研究报告数据';
