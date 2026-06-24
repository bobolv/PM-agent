from dataclasses import dataclass, field

from pm_agent.models import RoleType


@dataclass(frozen=True)
class PhaseSeed:
    name: str
    description: str


@dataclass(frozen=True)
class CatalogSeed:
    code: str
    phase_name: str | None
    name: str
    description: str
    outline_md: str
    role_type: RoleType
    sort_order: int
    is_periodic: bool = False
    period_type: str | None = None
    default_selected: bool = True
    dependency_codes: list[str] = field(default_factory=list)


DEFAULT_PHASES = [
    PhaseSeed("需求调研", "梳理项目背景、干系人诉求、业务流程、范围和约束。"),
    PhaseSeed("初步设计", "形成总体架构、技术路线、边界系统和关键方案。"),
    PhaseSeed("详细设计", "展开模块、接口、数据结构、安全和异常处理设计。"),
    PhaseSeed("调试测试", "围绕单元、模块和联调问题组织测试与缺陷闭环。"),
    PhaseSeed("集成测试", "验证跨系统流程、数据一致性、性能和稳定性。"),
    PhaseSeed("上线部署", "准备发布方案、部署步骤、回滚预案和上线检查。"),
    PhaseSeed("试运行", "跟踪运行指标、用户反馈、问题修复和优化建议。"),
    PhaseSeed("项目验收", "整理交付物、验收依据、测试结论和签收材料。"),
    PhaseSeed("系统运维", "沉淀运维手册、巡检机制、故障处理和持续改进。"),
]


def outline(title: str, sections: list[str]) -> str:
    return "# " + title + "\n\n" + "\n\n".join(f"## {section}\n" for section in sections)


DOCUMENT_CATALOG = [
    CatalogSeed(
        "req-stakeholder-map",
        "需求调研",
        "干系人清单与访谈计划",
        "明确调研对象、访谈安排、信息采集方式和沟通节奏。",
        outline("干系人清单与访谈计划", ["调研目标", "干系人清单", "访谈安排", "问题清单", "风险与准备"]),
        RoleType.researcher,
        101,
        dependency_codes=[],
    ),
    CatalogSeed(
        "req-research-minutes",
        "需求调研",
        "调研访谈纪要",
        "记录访谈事实、业务痛点、约束条件和待确认事项。",
        outline("调研访谈纪要", ["访谈对象", "访谈摘要", "业务现状", "关键诉求", "待确认问题"]),
        RoleType.researcher,
        102,
        dependency_codes=["req-stakeholder-map"],
        default_selected=False,
    ),
    CatalogSeed(
        "req-business-process",
        "需求调研",
        "业务流程与现状分析",
        "描述现行业务流程、系统边界、数据流和主要问题。",
        outline("业务流程与现状分析", ["业务背景", "现状流程", "系统边界", "问题分析", "改进机会"]),
        RoleType.researcher,
        103,
        dependency_codes=["req-research-minutes"],
    ),
    CatalogSeed(
        "req-report",
        "需求调研",
        "需求调研报告",
        "汇总业务需求、非功能需求、范围边界、风险和假设。",
        outline("需求调研报告", ["项目背景", "业务现状", "需求清单", "非功能需求", "范围边界", "风险与假设"]),
        RoleType.researcher,
        104,
        dependency_codes=["req-stakeholder-map", "req-business-process"],
    ),
    CatalogSeed(
        "req-scope-confirmation",
        "需求调研",
        "需求范围确认单",
        "用于确认本期建设范围、暂缓范围、验收口径和签认意见。",
        outline("需求范围确认单", ["确认范围", "暂缓范围", "验收口径", "变更机制", "确认意见"]),
        RoleType.project_owner,
        105,
        dependency_codes=["req-report"],
    ),
    CatalogSeed(
        "prelim-architecture",
        "初步设计",
        "初步设计说明书",
        "给出总体架构、功能划分、集成关系、关键技术路线和风险。",
        outline("初步设计说明书", ["设计依据", "总体架构", "功能划分", "数据流向", "集成关系", "风险与约束"]),
        RoleType.development_manager,
        201,
        dependency_codes=["req-report", "req-scope-confirmation"],
    ),
    CatalogSeed(
        "prelim-interface-list",
        "初步设计",
        "外部接口与系统边界清单",
        "明确外部系统、接口方向、数据对象、责任边界和联调约束。",
        outline("外部接口与系统边界清单", ["外部系统", "接口清单", "数据对象", "责任边界", "联调约束"]),
        RoleType.development_manager,
        202,
        dependency_codes=["req-report", "prelim-architecture"],
    ),
    CatalogSeed(
        "prelim-data-plan",
        "初步设计",
        "数据设计初稿",
        "形成核心实体、主数据、数据流、数据质量和迁移初步方案。",
        outline("数据设计初稿", ["核心实体", "主数据与来源", "数据流", "数据质量", "迁移考虑"]),
        RoleType.development_manager,
        203,
        dependency_codes=["req-report", "prelim-architecture"],
    ),
    CatalogSeed(
        "detail-module-design",
        "详细设计",
        "模块详细设计说明书",
        "展开模块职责、内部流程、异常处理、配置项和扩展点。",
        outline("模块详细设计说明书", ["模块划分", "模块职责", "内部流程", "异常处理", "配置与扩展", "可测试性设计"]),
        RoleType.development_manager,
        301,
        dependency_codes=["prelim-architecture", "prelim-interface-list", "prelim-data-plan"],
    ),
    CatalogSeed(
        "detail-api-spec",
        "详细设计",
        "接口详细设计说明书",
        "定义接口协议、请求响应、错误码、鉴权、幂等和兼容策略。",
        outline("接口详细设计说明书", ["接口总览", "请求响应", "错误码", "鉴权与权限", "幂等与兼容", "联调说明"]),
        RoleType.developer,
        302,
        dependency_codes=["prelim-interface-list", "detail-module-design"],
    ),
    CatalogSeed(
        "detail-db-design",
        "详细设计",
        "数据库设计说明书",
        "定义数据表、关系、索引、约束、迁移和数据保留策略。",
        outline("数据库设计说明书", ["实体关系", "表结构", "索引与约束", "数据迁移", "审计与保留"]),
        RoleType.developer,
        303,
        dependency_codes=["prelim-data-plan", "detail-module-design"],
    ),
    CatalogSeed(
        "debug-test-plan",
        "调试测试",
        "调试测试计划",
        "定义调试测试范围、环境、用例策略、入口出口准则。",
        outline("调试测试计划", ["测试范围", "测试环境", "用例策略", "入口准则", "出口准则", "风险"]),
        RoleType.test_engineer,
        401,
        dependency_codes=["detail-module-design", "detail-api-spec"],
    ),
    CatalogSeed(
        "debug-test-cases",
        "调试测试",
        "调试测试用例",
        "围绕模块、接口、异常和边界条件形成可执行用例。",
        outline("调试测试用例", ["用例范围", "前置条件", "测试步骤", "预期结果", "测试数据"]),
        RoleType.test_engineer,
        402,
        dependency_codes=["debug-test-plan", "detail-api-spec"],
    ),
    CatalogSeed(
        "debug-test-report",
        "调试测试",
        "调试测试报告",
        "汇总测试执行、缺陷、修复验证和阶段质量结论。",
        outline("调试测试报告", ["测试执行", "缺陷统计", "修复验证", "遗留问题", "质量结论"]),
        RoleType.test_engineer,
        403,
        dependency_codes=["debug-test-plan", "debug-test-cases"],
    ),
    CatalogSeed(
        "integration-test-plan",
        "集成测试",
        "集成测试方案",
        "定义跨系统业务链路、集成环境、数据准备和验证方法。",
        outline("集成测试方案", ["集成范围", "业务链路", "环境准备", "数据准备", "验证方法", "风险"]),
        RoleType.test_engineer,
        501,
        dependency_codes=["debug-test-report", "prelim-interface-list"],
    ),
    CatalogSeed(
        "integration-test-report",
        "集成测试",
        "集成测试报告",
        "记录集成测试执行、问题闭环、性能稳定性和上线建议。",
        outline("集成测试报告", ["执行概况", "问题与修复", "性能与稳定性", "遗留风险", "上线建议"]),
        RoleType.test_engineer,
        502,
        dependency_codes=["integration-test-plan", "debug-test-report"],
    ),
    CatalogSeed(
        "deploy-plan",
        "上线部署",
        "上线部署方案",
        "明确发布内容、部署步骤、验证清单、回滚预案和职责分工。",
        outline("上线部署方案", ["发布内容", "部署架构", "操作步骤", "验证清单", "回滚预案", "职责分工"]),
        RoleType.operations_engineer,
        601,
        dependency_codes=["integration-test-report", "detail-db-design"],
    ),
    CatalogSeed(
        "deploy-checklist",
        "上线部署",
        "上线检查清单",
        "用于上线前、中、后的逐项检查和签认。",
        outline("上线检查清单", ["上线前检查", "上线操作检查", "上线后验证", "异常处理", "签认记录"]),
        RoleType.operations_engineer,
        602,
        dependency_codes=["deploy-plan"],
    ),
    CatalogSeed(
        "trial-run-report",
        "试运行",
        "试运行报告",
        "跟踪运行指标、用户反馈、问题处理和优化建议。",
        outline("试运行报告", ["运行概况", "指标统计", "用户反馈", "问题处理", "优化建议"]),
        RoleType.operations_engineer,
        701,
        dependency_codes=["deploy-plan", "deploy-checklist"],
    ),
    CatalogSeed(
        "acceptance-plan",
        "项目验收",
        "验收方案",
        "明确验收依据、验收范围、验收材料、组织安排和通过准则。",
        outline("验收方案", ["验收依据", "验收范围", "验收材料", "组织安排", "通过准则"]),
        RoleType.project_manager,
        801,
        dependency_codes=["trial-run-report", "integration-test-report"],
    ),
    CatalogSeed(
        "acceptance-report",
        "项目验收",
        "验收报告",
        "汇总交付物、验收结论、遗留问题和签收意见。",
        outline("验收报告", ["验收依据", "交付物清单", "测试与试运行结论", "遗留问题", "验收意见"]),
        RoleType.project_owner,
        802,
        dependency_codes=["acceptance-plan", "trial-run-report"],
    ),
    CatalogSeed(
        "ops-manual",
        "系统运维",
        "运维手册",
        "沉淀系统信息、巡检、备份恢复、故障处理和维护流程。",
        outline("运维手册", ["系统概述", "部署信息", "巡检项", "备份恢复", "故障处理", "维护流程"]),
        RoleType.operations_engineer,
        901,
        dependency_codes=["deploy-plan", "trial-run-report"],
    ),
    CatalogSeed(
        "ops-emergency-plan",
        "系统运维",
        "应急处置预案",
        "定义常见故障、分级响应、处置流程、升级机制和复盘要求。",
        outline("应急处置预案", ["故障分级", "响应流程", "处置步骤", "升级机制", "复盘要求"]),
        RoleType.operations_engineer,
        902,
        dependency_codes=["ops-manual"],
    ),
    CatalogSeed(
        "weekly-report",
        None,
        "项目周报",
        "基于本周工作记录、风险问题、阶段文档和下周计划生成。",
        outline("项目周报", ["本周目标", "本周进展", "产出与证据", "风险问题", "下周计划"]),
        RoleType.project_manager,
        1001,
        is_periodic=True,
        period_type="weekly",
        dependency_codes=[],
    ),
    CatalogSeed(
        "monthly-report",
        None,
        "项目月报",
        "基于本月工作记录、里程碑、关键风险和下月计划生成。",
        outline("项目月报", ["月度目标", "关键进展", "里程碑状态", "风险与决策", "下月计划"]),
        RoleType.project_manager,
        1002,
        is_periodic=True,
        period_type="monthly",
        dependency_codes=[],
    ),
]

PERIODIC_TEMPLATES = [
    (item.name, item.period_type, item.outline_md)
    for item in DOCUMENT_CATALOG
    if item.is_periodic
]


DEFAULT_ROLES = [
    (
        RoleType.project_owner,
        "项目负责人",
        "代表业务和建设目标，对项目范围、价值、关键决策和验收结果负责。",
        "你是项目负责人，请关注业务价值、范围边界、关键决策和验收标准。",
    ),
    (
        RoleType.project_manager,
        "项目经理",
        "负责计划、进度、风险、沟通、交付物组织和跨角色协调。",
        "你是项目经理，请关注计划可执行性、里程碑、风险闭环和交付物完整性。",
    ),
    (
        RoleType.development_manager,
        "开发经理",
        "负责技术方案、开发计划、工程质量和研发资源协调。",
        "你是开发经理，请关注架构可落地性、模块边界、技术风险和工程实施。",
    ),
    (
        RoleType.developer,
        "开发工程师",
        "负责模块实现、接口联调、缺陷修复和技术细节沉淀。",
        "你是开发工程师，请关注实现细节、接口、数据结构、异常处理和可维护性。",
    ),
    (
        RoleType.test_engineer,
        "测试工程师",
        "负责测试计划、用例、缺陷跟踪、质量评估和测试报告。",
        "你是测试工程师，请关注测试范围、测试数据、验收口径、缺陷闭环和质量结论。",
    ),
    (
        RoleType.operations_engineer,
        "运维工程师",
        "负责部署、监控、备份恢复、运行保障和故障处置。",
        "你是运维工程师，请关注部署可操作性、监控指标、回滚预案和运维可持续性。",
    ),
    (
        RoleType.researcher,
        "研究人员",
        "负责调研、分析、资料整理、方案论证和趋势判断。",
        "你是研究人员，请关注事实依据、调研方法、约束条件和分析结论。",
    ),
]
