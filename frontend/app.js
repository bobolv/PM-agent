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
  runtime: null,
  selectedPhase: null,
  selectedPlan: null,
  preview: null,
  references: null,
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
    let message = error;
    try {
      message = JSON.parse(error).detail || error;
    } catch {
      // Keep the raw response text when it is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function byId(id) {
  return document.getElementById(id);
}

function bindClick(id, handler) {
  const element = byId(id);
  if (element) element.onclick = handler;
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
  if (page === "reference") ensureReferencePage();
  state.page = page;
  document.querySelectorAll(".page").forEach((element) => element.classList.remove("active"));
  byId(`${page}Page`).classList.add("active");
  byId("navProjects").classList.toggle("active", page === "projects");
  byId("navNewProject").classList.toggle("active", page === "wizard");
  byId("navSettings")?.classList.toggle("active", page === "settings");
  renderHeader();
  window.scrollTo(0, 0);
}

function renderHeader() {
  const titles = {
    projects: ["项目列表", "选择一个项目进入详情，或使用向导创建新项目。"],
    wizard: ["新建项目向导", "录入项目材料、确认角色，并从候选模板库中勾选文档。"],
    projectDetail: [state.project?.name || "项目详情", "查看项目角色、生命周期阶段和最近生成文档。"],
    phaseDetail: [state.selectedPhase?.name || "阶段详情", "查看当前阶段启用的文档清单。"],
    reference: [state.selectedPlan?.title || "引用关系管理", "管理生成前导入上下文的前序文档。"],
    preview: [state.selectedPlan?.title || "文档生成预览", "生成前检查 Prompt、引用文档和上下文材料。"],
    settings: ["全局设置", "管理模板库导出、批量导入和 Obsidian 互通。"],
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

function ensureReferencePage() {
  if (byId("referencePage")) return;
  const workspace = document.querySelector(".workspace");
  if (!workspace) return;
  workspace.insertAdjacentHTML(
    "beforeend",
    `
      <section id="referencePage" class="page">
        <div class="section-head">
          <div>
            <button id="backFromReference" class="link-button" type="button">返回文档清单</button>
            <h2>引用关系管理</h2>
            <p id="referenceTargetMeta" class="muted"></p>
          </div>
        </div>
        <div class="reference-target">
          <span>当前文档</span>
          <strong id="referenceTargetTitle">未选择文档</strong>
        </div>
        <div class="reference-layout">
          <div class="panel">
            <h2>已导入上下文的前序文档</h2>
            <p class="muted">生成预览会按这里的清单拉取已生成版本，并自动去重。</p>
            <div id="referenceList" class="reference-list"></div>
          </div>
          <div class="panel">
            <h2>添加引用文档</h2>
            <p class="muted">从本项目已启用文档中选择。未生成的文档可先建立关系，生成时若无版本会跳过。</p>
            <div class="reference-add">
              <select id="referenceCandidateSelect"></select>
              <button id="addReference" class="primary" type="button">添加到上下文</button>
            </div>
          </div>
        </div>
      </section>
    `,
  );
  bindClick("backFromReference", () => {
    showPage(state.selectedPlan?.is_periodic ? "projectDetail" : "phaseDetail");
  });
  bindClick("addReference", addReference);
  bindClick("addDocumentReference", addDocumentReference);
}

async function bootstrap() {
  await Promise.all([loadRuntime(), loadCatalog(), loadProjects()]);
  renderDefaultRoles();
  renderWizardCatalog();
  showPage("projects");
}

async function loadRuntime() {
  state.runtime = await request("/api/runtime");
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
  const rows = state.projects
    .map((project) => {
      const summary = escapeHtml(project.background).slice(0, 110) || "暂无背景";
      return `
        <tr>
          <td>
            <strong>${escapeHtml(project.name)}</strong>
            <span>${summary}</span>
          </td>
          <td>${project.start_date || "未设置"}</td>
          <td>${project.end_date || "未设置"}</td>
          <td><span class="status-pill neutral">进行中</span></td>
          <td class="table-actions">
            <button class="secondary compact-button" type="button" data-open-project="${project.id}">进入项目</button>
          </td>
        </tr>
      `;
    })
    .join("");
  target.innerHTML = `
    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>项目名称</th>
            <th>开始时间</th>
            <th>结束时间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
  target.querySelectorAll("[data-open-project]").forEach((button) => {
    button.onclick = () => openProject(Number(button.dataset.openProject));
  });
}

async function deleteProject(projectId) {
  const project = state.projects.find((item) => item.id === projectId);
  const name = project?.name || `项目 ${projectId}`;
  const warning = [
    `删除项目“${name}”会同时删除：`,
    "1. 项目阶段、任务和角色",
    "2. 文档计划、已生成文档和版本记录",
    "3. 与该项目关联的本地文档目录",
    "",
    "如需继续，请在下一步输入完整项目名称。",
  ].join("\n");
  if (!confirm(warning)) {
    return;
  }
  const typedName = prompt(`请输入项目名称以确认删除：${name}`);
  if (typedName !== name) {
    alert("项目名称不一致，已取消删除。");
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
    references: null,
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
  renderProjectDocumentPlans();
  renderPeriodicPlans();
  renderProjectRoles();
  renderRecentDocuments();
  renderProjectSettings();
}

function renderPhaseCards() {
  const rows = state.phases
    .map((phase) => {
      const plans = plansForPhase(phase.id);
      const generated = plans.filter((plan) => plan.status === "generated").length;
      return `
        <tr>
          <td><span class="phase-index">${phase.order_index}</span></td>
          <td>
            <strong>${escapeHtml(phase.name)}</strong>
            <span>${escapeHtml(phase.description)}</span>
          </td>
          <td>${plans.length}</td>
          <td>${generated}</td>
          <td class="table-actions">
            <button class="secondary compact-button" type="button" data-phase="${phase.id}">查看阶段</button>
          </td>
        </tr>
      `;
    })
    .join("");
  byId("phaseCards").innerHTML = `
    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>序号</th>
            <th>阶段</th>
            <th>启用文档</th>
            <th>已生成</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
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
  renderDocumentPlanTable("periodicPlans", plans, "暂无周期文档");
  bindDocumentPlanActions("periodicPlans");
}

function renderProjectDocumentPlans() {
  const plans = state.documentPlans
    .filter((plan) => !plan.is_periodic)
    .sort((a, b) => {
      const phaseA = state.phases.find((phase) => phase.id === a.phase_id)?.order_index || 999;
      const phaseB = state.phases.find((phase) => phase.id === b.phase_id)?.order_index || 999;
      return phaseA - phaseB || a.sort_order - b.sort_order;
    });
  renderDocumentPlanTable("projectDocumentPlans", plans, "暂无启用文档");
  bindDocumentPlanActions("projectDocumentPlans");
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

function renderProjectSettings() {
  byId("deleteCurrentProject").onclick = () => deleteProject(state.project.id);
  const phaseSelect = byId("importMdPhase");
  if (phaseSelect) {
    phaseSelect.innerHTML = state.phases
      .map((phase) => `<option value="${phase.id}">${escapeHtml(phase.name)}</option>`)
      .join("");
  }
  bindClick("importMdSubmit", importMarkdownDocument);
}

async function runTemplateLibraryAction(action, buttonId) {
  const button = byId(buttonId);
  const previousText = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = "处理中";
  }
  try {
    const result = await action();
    await loadCatalog();
    renderWizardCatalog();
    renderTemplateLibraryStatus(result);
  } catch (error) {
    showToast(`模板库操作失败：${error.message}`, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = previousText;
    }
  }
}

function renderTemplateLibraryStatus(result) {
  const target = byId("templateLibraryStatus");
  if (!target) return;
  const paths = result.paths || [];
  const countText = [
    result.exported !== undefined ? `导出 ${result.exported} 个文件` : "",
    result.synced !== undefined ? `同步 ${result.synced} 个模板` : "",
    result.reset !== undefined ? `重置 ${result.reset} 个内置模板` : "",
  ]
    .filter(Boolean)
    .join("，");
  target.innerHTML = `
    <strong>${escapeHtml(countText || "操作完成")}</strong>
    <span>${paths.length ? `最近文件：${escapeHtml(paths.slice(0, 3).join("；"))}` : "模板目录已处理完成。"}</span>
  `;
  showToast(countText || "模板库操作完成。", "success");
}

function bindTemplateLibrarySettings() {
  bindClick("exportTemplates", () =>
    runTemplateLibraryAction(
      () => request("/api/document-catalog/export-md", { method: "POST" }),
      "exportTemplates",
    ),
  );
  bindClick("exportTemplatesOverwrite", () =>
    runTemplateLibraryAction(
      () => request("/api/document-catalog/export-md?overwrite=true", { method: "POST" }),
      "exportTemplatesOverwrite",
    ),
  );
  bindClick("syncTemplates", () =>
    runTemplateLibraryAction(
      () => request("/api/document-catalog/sync-md", { method: "POST" }),
      "syncTemplates",
    ),
  );
  bindClick("resetBuiltinTemplates", () => {
    if (!confirm("将用内置目录重置模板元数据并覆盖导出 Markdown，确认继续？")) return;
    runTemplateLibraryAction(
      () => request("/api/document-catalog/reset-builtin-md", { method: "POST" }),
      "resetBuiltinTemplates",
    );
  });
}

async function importMarkdownDocument() {
  if (!state.project) return;
  const fileInput = byId("importMdFile");
  const file = fileInput?.files?.[0];
  if (!file) {
    showToast("请选择一个 Markdown 文件。", "error");
    return;
  }
  const importAsDocument = byId("importAsDocument")?.checked ?? true;
  const importAsTemplate = byId("importAsTemplate")?.checked ?? true;
  if (!importAsDocument && !importAsTemplate) {
    showToast("请至少选择一种导入用途。", "error");
    return;
  }

  const button = byId("importMdSubmit");
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = "正在导入";
  try {
    const content = await file.text();
    await request(`/api/projects/${state.project.id}/imports/md`, {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_md: content,
        phase_id: Number(byId("importMdPhase").value) || null,
        template_name: value("importMdName") || null,
        import_as_template: importAsTemplate,
        import_as_reference_document: importAsDocument,
      }),
    });
    byId("importMdName").value = "";
    fileInput.value = "";
    await loadCatalog();
    await openProject(state.project.id);
    showToast("MD 文档已导入，模板提纲和关联文件已更新。", "success");
  } catch (error) {
    showToast(`导入失败：${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = previousText || "导入文档";
  }
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
  renderDocumentPlanTable("phaseDocumentPlans", plans, "该阶段暂无启用文档");
  bindDocumentPlanActions("phaseDocumentPlans");
}

function renderDocumentPlanTable(targetId, plans, emptyText) {
  const target = byId(targetId);
  if (!plans.length) {
    target.innerHTML = `<div class="empty-state compact-empty"><h2>${escapeHtml(emptyText)}</h2><p>可以在新建项目时从候选库勾选更多文档。</p></div>`;
    return;
  }
  target.innerHTML = `
    <div class="document-list">
      ${plans.map(renderDocumentPlanRow).join("")}
    </div>
  `;
}

function renderDocumentPlanRow(plan) {
  const role = state.roles.find((item) => item.id === plan.role_id);
  const generated = state.documents.find((doc) => doc.plan_id === plan.id);
  const phase = state.phases.find((item) => item.id === plan.phase_id);
  const dependencies = dependencyDisplayNames(plan);
  const dependencyBadges = dependencies.length
    ? dependencies.map((name) => `<span>${escapeHtml(name)}</span>`).join("")
    : "<span>无显式依赖</span>";
  return `
    <article class="document-row">
      <div class="document-main">
        <h3>${escapeHtml(plan.title)}</h3>
        <p>${escapeHtml(plan.description)}</p>
        <div class="dependency-row">${dependencyBadges}</div>
      </div>
      <div class="document-meta">
        <span><b>阶段</b>${escapeHtml(plan.is_periodic ? "周期文档" : phase?.name || "未设置")}</span>
        <span><b>角色</b>${escapeHtml(role?.name || "未设置")}</span>
        <span><b>版本</b>${generated ? formatDate(generated.updated_at) : "暂无"}</span>
      </div>
      <div class="document-actions">
        <span class="status-pill ${plan.status}">${statusLabel(plan.status)}</span>
        <button class="secondary compact-button" type="button" data-reference-plan="${plan.id}">
          管理引用
        </button>
        <button class="primary compact-button" type="button" data-preview-plan="${plan.id}">
          ${generated ? "预览/再生成" : "预览/生成"}
        </button>
      </div>
    </article>
  `;
}

function bindDocumentPlanActions(targetId) {
  const target = byId(targetId);
  target.querySelectorAll("[data-preview-plan]").forEach((button) => {
    button.onclick = () => openPreview(Number(button.dataset.previewPlan));
  });
  target.querySelectorAll("[data-reference-plan]").forEach((button) => {
    button.onclick = () => openReferenceManager(Number(button.dataset.referencePlan));
  });
}

function dependencyDisplayNames(plan) {
  const names = [];
  const seen = new Set();
  const addName = (name) => {
    if (!name || seen.has(name)) return;
    seen.add(name);
    names.push(name);
  };
  (plan.dependency_plan_ids || []).forEach((id) => {
    const dependency = state.documentPlans.find((item) => item.id === id);
    addName(dependency?.title);
  });
  if (!names.length) {
    (plan.dependency_codes || []).forEach((code) => {
      const dependency = state.documentPlans.find((item) => item.code === code);
      addName(dependency?.title || code);
    });
  }
  return names;
}

async function openReferenceManager(planId) {
  try {
    state.selectedPlan = state.documentPlans.find((plan) => plan.id === planId);
    if (state.selectedPlan?.phase_id) {
      state.selectedPhase = state.phases.find((phase) => phase.id === state.selectedPlan.phase_id);
      if (state.selectedPhase) renderPhaseDetail();
    }
    state.references = await request(`/api/document-plans/${planId}/references`);
    renderReferenceManager();
    showPage("reference");
  } catch (error) {
    showToast(`引用关系加载失败：${error.message}`, "error");
  }
}

function renderReferenceManager() {
  ensureReferencePage();
  if (!state.references) return;
  const references = state.references.references || [];
  const referenceIds = new Set(references.map((item) => item.id));
  const candidates = (state.references.candidates || []).filter((item) => !referenceIds.has(item.id));
  const documentReferences = state.references.document_references || [];
  const documentReferenceIds = new Set(documentReferences.map((item) => item.id));
  const documentCandidates = (state.references.document_candidates || []).filter(
    (item) => !documentReferenceIds.has(item.id),
  );
  if (!byId("referenceTargetTitle") || !byId("referenceList")) {
    showToast("引用关系页面结构加载失败，请刷新页面后重试。", "error");
    return;
  }
  byId("referenceTargetTitle").textContent = state.references.plan.title;
  byId("referenceTargetMeta").textContent = planPhaseText(state.references.plan);
  byId("referenceList").innerHTML = references.length
    ? references.map(renderReferenceItem).join("")
    : `<div class="empty-note">暂无显式引用。生成时会根据阶段回退策略选择前序文档。</div>`;
  if (byId("referenceDocumentList")) {
    byId("referenceDocumentList").innerHTML = documentReferences.length
      ? documentReferences.map(renderDocumentReferenceItem).join("")
      : `<div class="empty-note">暂无已导入的关联文件。</div>`;
  }
  byId("referenceCandidateSelect").innerHTML = candidates.length
    ? candidates.map((item) => `<option value="${item.id}">${escapeHtml(item.title)} · ${escapeHtml(planPhaseText(item))}</option>`).join("")
    : `<option value="">暂无可添加文档</option>`;
  byId("addReference").disabled = !candidates.length;
  if (byId("referenceDocumentCandidateSelect")) {
    byId("referenceDocumentCandidateSelect").innerHTML = documentCandidates.length
      ? documentCandidates
          .map((item) => `<option value="${item.id}">${escapeHtml(item.title)} · ${escapeHtml(item.phase_name || "未设置阶段")}</option>`)
          .join("")
      : `<option value="">暂无可添加关联文件</option>`;
    byId("addDocumentReference").disabled = !documentCandidates.length;
  }
  byId("referenceList").querySelectorAll("[data-remove-reference]").forEach((button) => {
    button.onclick = () => removeReference(Number(button.dataset.removeReference));
  });
  byId("referenceDocumentList")?.querySelectorAll("[data-remove-document-reference]").forEach((button) => {
    button.onclick = () => removeDocumentReference(Number(button.dataset.removeDocumentReference));
  });
}

function renderReferenceItem(item) {
  return `
    <div class="reference-item">
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(planPhaseText(item))} · ${statusLabel(item.status)}</span>
      </div>
      <button class="secondary compact-button" type="button" data-remove-reference="${item.id}">移除</button>
    </div>
  `;
}

function renderDocumentReferenceItem(item) {
  return `
    <div class="reference-item">
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.phase_name || "未设置阶段")} · ${statusLabel(item.status)}</span>
      </div>
      <button class="secondary compact-button" type="button" data-remove-document-reference="${item.id}">移除</button>
    </div>
  `;
}

function planPhaseText(plan) {
  return plan.is_periodic ? "周期文档" : plan.phase_name || "未设置阶段";
}

async function addReference() {
  const selectedId = Number(byId("referenceCandidateSelect").value);
  if (!selectedId) return;
  const ids = [...(state.references.references || []).map((item) => item.id), selectedId];
  await saveReferences(ids, (state.references.document_references || []).map((item) => item.id));
}

async function removeReference(referenceId) {
  const ids = (state.references.references || [])
    .map((item) => item.id)
    .filter((id) => id !== referenceId);
  await saveReferences(ids, (state.references.document_references || []).map((item) => item.id));
}

async function addDocumentReference() {
  const selectedId = Number(byId("referenceDocumentCandidateSelect")?.value);
  if (!selectedId) return;
  const ids = [...(state.references.document_references || []).map((item) => item.id), selectedId];
  await saveReferences((state.references.references || []).map((item) => item.id), ids);
}

async function removeDocumentReference(referenceId) {
  const ids = (state.references.document_references || [])
    .map((item) => item.id)
    .filter((id) => id !== referenceId);
  await saveReferences((state.references.references || []).map((item) => item.id), ids);
}

async function saveReferences(referenceIds, documentReferenceIds) {
  const result = await request(`/api/document-plans/${state.selectedPlan.id}/references`, {
    method: "PUT",
    body: JSON.stringify({
      dependency_plan_ids: referenceIds,
      reference_document_ids: documentReferenceIds,
    }),
  });
  state.references = result;
  const localPlan = state.documentPlans.find((plan) => plan.id === state.selectedPlan.id);
  if (localPlan) {
    localPlan.dependency_plan_ids = result.references.map((item) => item.id);
    localPlan.dependency_codes = result.references.map((item) => item.code);
    localPlan.reference_document_ids = result.document_references.map((item) => item.id);
    state.selectedPlan = localPlan;
  }
  renderReferenceManager();
  showToast("引用关系已更新，生成预览会使用新的上下文导入策略。", "success");
}

async function openPreview(planId) {
  try {
    state.selectedPlan = state.documentPlans.find((plan) => plan.id === planId);
    if (state.selectedPlan?.phase_id) {
      state.selectedPhase = state.phases.find((phase) => phase.id === state.selectedPlan.phase_id);
      if (state.selectedPhase) renderPhaseDetail();
    }
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
  } catch (error) {
    showToast(`预览加载失败：${error.message}`, "error");
  }
}

function renderPreview() {
  const generated = state.documents.find((doc) => doc.plan_id === state.selectedPlan.id);
  const runtime = state.runtime;
  const keyConfigured = Boolean(runtime?.api_key_configured ?? runtime?.openai_configured);
  const providerLabel = runtime ? `${runtime.llm_provider} · ${runtime.llm_model}` : "模型配置未知";
  const modelStatus = keyConfigured
    ? `将调用模型：${providerLabel}`
    : "未配置当前模型 API Key，将生成离线草稿";
  byId("previewTitle").textContent = state.selectedPlan.title;
  byId("previewMeta").textContent = `负责角色：${state.preview.role_name} · ${modelStatus}`;
  byId("generateFromPreview").textContent = generated ? "重新生成新版本" : "生成文档版本";
  byId("generationStatus").innerHTML = `
    <div class="status-card ${keyConfigured ? "model-ready" : "model-offline"}">
      <strong>${keyConfigured ? "模型调用就绪" : "离线草稿模式"}</strong>
      <span>${keyConfigured ? escapeHtml(runtime.llm_base_url) : "配置当前 provider 的 API Key 并重启后端后，会调用真实模型。"}</span>
      <span>${generated ? `当前文档已生成，点击按钮会新增版本。最近更新：${formatDate(generated.updated_at)}` : "当前文档尚未生成，点击按钮会创建第一个版本。"}</span>
    </div>
  `;
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
  const previousText = button.textContent;
  const keyConfigured = Boolean(state.runtime?.api_key_configured ?? state.runtime?.openai_configured);
  button.disabled = true;
  button.textContent = keyConfigured ? "正在调用模型" : "正在生成离线草稿";
  try {
    const document = await request("/api/documents/generate", {
      method: "POST",
      body: JSON.stringify({
        plan_id: state.selectedPlan.id,
        extra_instruction: "请突出当前阶段目标、前序文档继承关系、角色职责和可执行交付物。",
      }),
    });
    showToast(
      keyConfigured
        ? `生成成功：已调用 ${state.runtime.llm_model}，文档版本已更新。`
        : "生成成功：当前为离线草稿，配置 API Key 后可重新生成正式版本。",
      "success",
    );
    await openProject(state.project.id);
    if (!isPeriodic && phaseId) openPhase(phaseId);
    return document;
  } catch (error) {
    showToast(`生成失败：${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = previousText || "生成文档版本";
  }
}

function showToast(message, type = "success") {
  const toast = byId("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 5200);
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

bindClick("navProjects", () => showPage("projects"));
bindClick("navNewProject", openWizard);
bindClick("navSettings", () => showPage("settings"));
bindClick("backToProjects", () => showPage("projects"));
bindClick("backToProjectDetail", () => showPage("projectDetail"));
bindClick("backFromReference", () => {
  showPage(state.selectedPlan?.is_periodic ? "projectDetail" : "phaseDetail");
});
bindClick("backToPhaseDetail", () => {
  showPage(state.selectedPlan?.is_periodic ? "projectDetail" : "phaseDetail");
});
bindClick("generateFromPreview", generateFromPreview);
bindClick("addReference", addReference);
bindClick("addDocumentReference", addDocumentReference);
bindTemplateLibrarySettings();

document.querySelectorAll(".step").forEach((button) => {
  button.onclick = () => {
    state.wizardStep = Number(button.dataset.step);
    renderWizardStep();
  };
});

bindClick("prevWizard", () => {
  state.wizardStep = Math.max(1, state.wizardStep - 1);
  renderWizardStep();
});

bindClick("nextWizard", () => {
  state.wizardStep = Math.min(3, state.wizardStep + 1);
  renderWizardStep();
});

bindClick("submitProject", submitProject);

bindClick("selectDefaultDocs", () => {
  state.selectedDocumentCodes = new Set(
    state.catalog.filter((item) => item.default_selected).map((item) => item.code),
  );
  renderWizardCatalog();
});

bindClick("selectAllDocs", () => {
  state.selectedDocumentCodes = new Set(state.catalog.map((item) => item.code));
  renderWizardCatalog();
});

bootstrap().catch((error) => {
  console.error(error);
  alert("页面初始化失败，请确认后端服务已启动。");
});
