const state = {
  page: "projects",
  wizardStep: 1,
  projects: [],
  catalog: [],
  selectedDocumentCodes: new Set(),
  project: null,
  phases: [],
  roles: [],
  tasks: [],
  documentPlans: [],
  documents: [],
  selectedPhase: null,
  selectedPlan: null,
  preview: null,
};

const defaultRoles = [
  ["项目负责人", "代表业务和建设目标，对范围、价值和验收结果负责。"],
  ["项目经理", "负责计划、进度、风险、沟通和交付物组织。"],
  ["开发经理", "负责技术方案、工程质量和研发资源协调。"],
  ["开发工程师", "负责模块实现、接口联调、缺陷修复和技术细节。"],
  ["测试工程师", "负责测试计划、用例、缺陷跟踪和质量评估。"],
  ["运维工程师", "负责部署、监控、备份恢复和故障处置。"],
  ["研究人员", "负责调研、分析、资料整理和方案论证。"],
];

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error);
  }
  return response.json();
}

function byId(id) {
  return document.getElementById(id);
}

function value(id) {
  return byId(id).value.trim();
}

function escapeHtml(text) {
  return String(text ?? "").replace(
    /[&<>"]/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char],
  );
}

function showPage(page) {
  state.page = page;
  document.querySelectorAll(".page").forEach((element) => element.classList.remove("active"));
  byId(`${page}Page`).classList.add("active");
  byId("navProjects").classList.toggle("active", page === "projects");
  byId("navNewProject").classList.toggle("active", page === "wizard");
  renderHeader();
  window.scrollTo(0, 0);
}

function renderHeader() {
  const titles = {
    projects: ["项目列表", "选择一个项目进入详情，或使用向导创建新项目。"],
    wizard: ["新建项目向导", "录入项目材料、确认角色，并从候选模板库中勾选文档。"],
    projectDetail: [state.project?.name || "项目详情", "查看项目角色、生命周期阶段和最近生成文档。"],
    phaseDetail: [state.selectedPhase?.name || "阶段详情", "查看当前阶段启用的文档清单。"],
    preview: [state.selectedPlan?.title || "文档生成预览", "生成前检查 Prompt、引用文档和上下文材料。"],
  };
  const [title, subtitle] = titles[state.page] || titles.projects;
  byId("pageTitle").textContent = title;
  byId("pageSubtitle").textContent = subtitle;
  byId("headerActions").innerHTML =
    state.page === "projects"
      ? `<button class="primary" type="button" data-action="new-project">新建项目</button>`
      : "";
  const action = byId("headerActions").querySelector("[data-action='new-project']");
  if (action) action.onclick = openWizard;
}

async function bootstrap() {
  await Promise.all([loadCatalog(), loadProjects()]);
  renderDefaultRoles();
  renderWizardCatalog();
  showPage("projects");
}

async function loadCatalog() {
  state.catalog = await request("/api/document-catalog");
  state.selectedDocumentCodes = new Set(
    state.catalog.filter((item) => item.default_selected).map((item) => item.code),
  );
}

async function loadProjects() {
  state.projects = await request("/api/projects");
  renderProjectList();
  renderProjectCards();
}

function renderProjectList() {
  const target = byId("projectList");
  if (!state.projects.length) {
    target.innerHTML = `<div class="empty-note">暂无项目</div>`;
    return;
  }
  target.innerHTML = state.projects
    .map(
      (project) => `
        <button class="project-pill ${project.id === state.project?.id ? "active" : ""}" data-project="${project.id}" type="button">
          <span>${escapeHtml(project.name)}</span>
          <small>${project.start_date || "未设置"} 至 ${project.end_date || "未设置"}</small>
        </button>
      `,
    )
    .join("");
  target.querySelectorAll("[data-project]").forEach((button) => {
    button.onclick = () => openProject(Number(button.dataset.project));
  });
}

function renderProjectCards() {
  const target = byId("projectCards");
  if (!state.projects.length) {
    target.innerHTML = `
      <div class="empty-state">
        <h2>还没有项目</h2>
        <p>先通过新建项目向导录入背景、需求材料，并选择本项目启用的文档清单。</p>
        <button class="primary" type="button" data-action="new-project">新建项目</button>
      </div>
    `;
    target.querySelector("[data-action='new-project']").onclick = openWizard;
    return;
  }
  target.innerHTML = state.projects
    .map(
      (project) => `
        <article class="project-card">
          <div class="card-title">${escapeHtml(project.name)}</div>
          <p>${escapeHtml(project.background).slice(0, 150) || "暂无背景"}</p>
          <div class="card-meta">${project.start_date || "未设置"} 至 ${project.end_date || "未设置"}</div>
          <div class="card-actions">
            <button class="secondary" type="button" data-open-project="${project.id}">进入项目</button>
            <button class="danger" type="button" data-delete-project="${project.id}">删除</button>
          </div>
        </article>
      `,
    )
    .join("");
  target.querySelectorAll("[data-open-project]").forEach((button) => {
    button.onclick = () => openProject(Number(button.dataset.openProject));
  });
  target.querySelectorAll("[data-delete-project]").forEach((button) => {
    button.onclick = () => deleteProject(Number(button.dataset.deleteProject));
  });
}

async function deleteProject(projectId) {
  const project = state.projects.find((item) => item.id === projectId);
  const name = project?.name || `项目 ${projectId}`;
  if (!confirm(`确认删除“${name}”？该操作会删除项目阶段、任务、文档计划、生成文档和版本记录。`)) {
    return;
  }
  await request(`/api/projects/${projectId}`, { method: "DELETE" });
  if (state.project?.id === projectId) {
    Object.assign(state, {
      project: null,
      phases: [],
      roles: [],
      tasks: [],
      documentPlans: [],
      documents: [],
      selectedPhase: null,
      selectedPlan: null,
      preview: null,
    });
    showPage("projects");
  }
  await loadProjects();
}

function openWizard() {
  state.wizardStep = 1;
  resetWizard();
  renderWizardStep();
  showPage("wizard");
}

function resetWizard() {
  byId("projectName").value = "";
  byId("projectStart").value = "";
  byId("projectEnd").value = "";
  byId("projectBackground").value = "";
  byId("projectRequirements").value = "";
  byId("projectTasks").value = "";
  state.selectedDocumentCodes = new Set(
    state.catalog.filter((item) => item.default_selected).map((item) => item.code),
  );
  renderWizardCatalog();
}

function renderWizardStep() {
  document.querySelectorAll(".step").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.step) === state.wizardStep);
  });
  document.querySelectorAll(".wizard-panel").forEach((panel, index) => {
    panel.classList.toggle("active", index + 1 === state.wizardStep);
  });
  byId("prevWizard").disabled = state.wizardStep === 1;
  byId("nextWizard").classList.toggle("hidden", state.wizardStep === 3);
  byId("submitProject").classList.toggle("hidden", state.wizardStep !== 3);
}

function renderDefaultRoles() {
  byId("defaultRoleList").innerHTML = defaultRoles
    .map(
      ([name, description]) => `
        <article class="role-card">
          <strong>${name}</strong>
          <p>${description}</p>
        </article>
      `,
    )
    .join("");
}

function renderWizardCatalog() {
  const groups = groupBy(state.catalog, (item) => item.phase_name || "周期文档");
  byId("catalogChecklist").innerHTML = Object.entries(groups)
    .map(
      ([group, items]) => `
        <section class="catalog-group">
          <div class="group-head">
            <h3>${escapeHtml(group)}</h3>
            <span>${items.length} 个候选文档</span>
          </div>
          <div class="check-list">
            ${items
              .map(
                (item) => `
                  <label class="check-item">
                    <input type="checkbox" value="${escapeHtml(item.code)}" ${state.selectedDocumentCodes.has(item.code) ? "checked" : ""} />
                    <span>
                      <strong>${escapeHtml(item.name)}</strong>
                      <small>${escapeHtml(item.description)}</small>
                    </span>
                  </label>
                `,
              )
              .join("")}
          </div>
        </section>
      `,
    )
    .join("");
  byId("catalogChecklist").querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.onchange = () => {
      if (checkbox.checked) state.selectedDocumentCodes.add(checkbox.value);
      else state.selectedDocumentCodes.delete(checkbox.value);
    };
  });
}

async function submitProject() {
  const payload = {
    name: value("projectName"),
    background: value("projectBackground"),
    requirements: value("projectRequirements"),
    start_date: value("projectStart") || null,
    end_date: value("projectEnd") || null,
    tasks: value("projectTasks")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    selected_document_codes: [...state.selectedDocumentCodes],
  };
  if (!payload.name || !payload.background || !payload.requirements) {
    alert("请填写项目名称、项目背景和需求材料。");
    state.wizardStep = 1;
    renderWizardStep();
    return;
  }
  if (!payload.selected_document_codes.length) {
    alert("请至少选择一个候选文档。");
    return;
  }
  const project = await request("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadProjects();
  await openProject(project.id);
}

async function openProject(projectId) {
  const [project, roles, phases, plans, documents, tasks] = await Promise.all([
    request(`/api/projects/${projectId}`),
    request(`/api/projects/${projectId}/roles`),
    request(`/api/projects/${projectId}/phases`),
    request(`/api/projects/${projectId}/document-plans`),
    request(`/api/projects/${projectId}/documents`),
    request(`/api/projects/${projectId}/tasks`),
  ]);
  Object.assign(state, {
    project,
    roles,
    phases,
    documentPlans: plans,
    documents,
    tasks,
    selectedPhase: null,
    selectedPlan: null,
    preview: null,
  });
  renderProjectList();
  renderProjectDetail();
  showPage("projectDetail");
}

function renderProjectDetail() {
  byId("detailProjectName").textContent = state.project.name;
  byId("detailProjectMeta").textContent = `${state.project.start_date || "未设置"} 至 ${state.project.end_date || "未设置"}`;
  byId("projectSummary").innerHTML = `
    <article class="metric-card"><strong>${state.phases.length}</strong><span>生命周期阶段</span></article>
    <article class="metric-card"><strong>${state.documentPlans.length}</strong><span>启用文档</span></article>
    <article class="metric-card"><strong>${state.documents.length}</strong><span>已生成文档</span></article>
    <article class="metric-card"><strong>${state.tasks.length}</strong><span>项目任务</span></article>
  `;
  renderPhaseCards();
  renderPeriodicPlans();
  renderProjectRoles();
  renderRecentDocuments();
}

function renderPhaseCards() {
  byId("phaseCards").innerHTML = state.phases
    .map((phase) => {
      const plans = plansForPhase(phase.id);
      const generated = plans.filter((plan) => plan.status === "generated").length;
      return `
        <article class="phase-card">
          <div class="phase-index">${phase.order_index}</div>
          <div>
            <h3>${escapeHtml(phase.name)}</h3>
            <p>${escapeHtml(phase.description)}</p>
            <div class="card-meta">${plans.length} 份启用文档，${generated} 份已生成</div>
          </div>
          <button class="secondary" type="button" data-phase="${phase.id}">查看阶段</button>
        </article>
      `;
    })
    .join("");
  byId("phaseCards").querySelectorAll("[data-phase]").forEach((button) => {
    button.onclick = () => openPhase(Number(button.dataset.phase));
  });
}

function renderProjectRoles() {
  byId("projectRoles").innerHTML = state.roles
    .map(
      (role) => `
        <div class="compact-item">
          <strong>${escapeHtml(role.name)}</strong>
          <span>${escapeHtml(role.responsibility)}</span>
        </div>
      `,
    )
    .join("");
}

function renderPeriodicPlans() {
  const plans = state.documentPlans
    .filter((plan) => plan.is_periodic)
    .sort((a, b) => a.sort_order - b.sort_order);
  byId("periodicPlans").innerHTML = plans.length
    ? plans.map(renderDocumentPlanCard).join("")
    : `<div class="empty-note">暂无周期文档</div>`;
  byId("periodicPlans").querySelectorAll("[data-preview-plan]").forEach((button) => {
    button.onclick = () => openPreview(Number(button.dataset.previewPlan));
  });
}


function renderRecentDocuments() {
  const recent = state.documents.slice(0, 6);
  byId("recentDocuments").innerHTML = recent.length
    ? recent
        .map(
          (doc) => `
            <div class="compact-item">
              <strong>${escapeHtml(doc.title)}</strong>
              <span>${escapeHtml(doc.status)} · ${formatDate(doc.updated_at)}</span>
            </div>
          `,
        )
        .join("")
    : `<div class="empty-note">暂无生成文档</div>`;
}

function openPhase(phaseId) {
  state.selectedPhase = state.phases.find((phase) => phase.id === phaseId);
  renderPhaseDetail();
  showPage("phaseDetail");
}

function renderPhaseDetail() {
  byId("phaseTitle").textContent = state.selectedPhase.name;
  byId("phaseDescription").textContent = state.selectedPhase.description;
  const plans = plansForPhase(state.selectedPhase.id);
  byId("phaseDocumentPlans").innerHTML = plans.length
    ? plans.map(renderDocumentPlanCard).join("")
    : `<div class="empty-state"><h2>该阶段暂无启用文档</h2><p>可以在新建项目时从候选库勾选更多文档。</p></div>`;
  byId("phaseDocumentPlans").querySelectorAll("[data-preview-plan]").forEach((button) => {
    button.onclick = () => openPreview(Number(button.dataset.previewPlan));
  });
}

function renderDocumentPlanCard(plan) {
  const role = state.roles.find((item) => item.id === plan.role_id);
  const generated = state.documents.find((doc) => doc.plan_id === plan.id);
  return `
    <article class="document-plan-card">
      <div class="doc-status ${plan.status}">${statusLabel(plan.status)}</div>
      <h3>${escapeHtml(plan.title)}</h3>
      <p>${escapeHtml(plan.description)}</p>
      <div class="dependency-row">
        ${plan.dependency_codes.length ? plan.dependency_codes.map((code) => `<span>${escapeHtml(code)}</span>`).join("") : "<span>无显式依赖</span>"}
      </div>
      <div class="card-meta">负责角色：${escapeHtml(role?.name || "未设置")} ${generated ? ` · 最近生成：${formatDate(generated.updated_at)}` : ""}</div>
      <button class="primary" type="button" data-preview-plan="${plan.id}">预览 Prompt</button>
    </article>
  `;
}

async function openPreview(planId) {
  state.selectedPlan = state.documentPlans.find((plan) => plan.id === planId);
  state.preview = await request("/api/documents/preview", {
    method: "POST",
    body: JSON.stringify({
      plan_id: planId,
      extra_instruction: "请突出当前阶段目标、前序文档继承关系、角色职责和可执行交付物。",
    }),
  });
  renderPreview();
  byId("backToPhaseDetail").textContent = state.selectedPlan.is_periodic ? "返回项目详情" : "返回阶段详情";
  showPage("preview");
}

function renderPreview() {
  byId("previewTitle").textContent = state.selectedPlan.title;
  byId("previewMeta").textContent = `负责角色：${state.preview.role_name}`;
  byId("systemPrompt").textContent = state.preview.system_prompt;
  byId("userPrompt").textContent = state.preview.user_prompt;
  byId("contextPreview").textContent = state.preview.context_md;
  byId("sourceBadges").innerHTML = `
    <span>引用文档 ${state.preview.source_document_ids.length}</span>
    <span>工作记录 ${state.preview.source_work_record_ids.length}</span>
    <span>历史任务产物 ${state.preview.source_artifact_ids.length}</span>
  `;
}

async function generateFromPreview() {
  if (!state.selectedPlan) return;
  const phaseId = state.selectedPhase?.id;
  const isPeriodic = state.selectedPlan.is_periodic;
  const button = byId("generateFromPreview");
  button.disabled = true;
  button.textContent = "生成中";
  try {
    await request("/api/documents/generate", {
      method: "POST",
      body: JSON.stringify({
        plan_id: state.selectedPlan.id,
        extra_instruction: "请突出当前阶段目标、前序文档继承关系、角色职责和可执行交付物。",
      }),
    });
    await openProject(state.project.id);
    if (!isPeriodic && phaseId) openPhase(phaseId);
  } finally {
    button.disabled = false;
    button.textContent = "生成文档版本";
  }
}

function plansForPhase(phaseId) {
  return state.documentPlans
    .filter((plan) => plan.phase_id === phaseId && !plan.is_periodic)
    .sort((a, b) => a.sort_order - b.sort_order);
}

function groupBy(items, getKey) {
  return items.reduce((groups, item) => {
    const key = getKey(item);
    groups[key] ||= [];
    groups[key].push(item);
    return groups;
  }, {});
}

function formatDate(value) {
  if (!value) return "未设置";
  return String(value).slice(0, 10);
}

function statusLabel(status) {
  return {
    planned: "待生成",
    skipped: "已跳过",
    in_progress: "生成中",
    generated: "已生成",
    approved: "已确认",
  }[status] || status;
}

byId("navProjects").onclick = () => showPage("projects");
byId("navNewProject").onclick = openWizard;
byId("backToProjects").onclick = () => showPage("projects");
byId("backToProjectDetail").onclick = () => showPage("projectDetail");
byId("backToPhaseDetail").onclick = () => {
  showPage(state.selectedPlan?.is_periodic ? "projectDetail" : "phaseDetail");
};
byId("generateFromPreview").onclick = generateFromPreview;

document.querySelectorAll(".step").forEach((button) => {
  button.onclick = () => {
    state.wizardStep = Number(button.dataset.step);
    renderWizardStep();
  };
});

byId("prevWizard").onclick = () => {
  state.wizardStep = Math.max(1, state.wizardStep - 1);
  renderWizardStep();
};

byId("nextWizard").onclick = () => {
  state.wizardStep = Math.min(3, state.wizardStep + 1);
  renderWizardStep();
};

byId("submitProject").onclick = submitProject;

byId("selectDefaultDocs").onclick = () => {
  state.selectedDocumentCodes = new Set(
    state.catalog.filter((item) => item.default_selected).map((item) => item.code),
  );
  renderWizardCatalog();
};

byId("selectAllDocs").onclick = () => {
  state.selectedDocumentCodes = new Set(state.catalog.map((item) => item.code));
  renderWizardCatalog();
};

bootstrap().catch((error) => {
  console.error(error);
  alert("页面初始化失败，请确认后端服务已启动。");
});
