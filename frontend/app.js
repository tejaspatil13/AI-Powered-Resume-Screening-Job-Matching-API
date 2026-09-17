const API_URL = "https://ai-powered-resume-screening-job-matching-d816.onrender.com";


/* =========================================================
   HELPERS
========================================================= */

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      body.detail ||
      body.message ||
      `Request failed (${response.status})`
    );
  }

  return body;
}

function formatTitle(title = "") {
  return title.replaceAll("_", " ");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[character]));
}

function showError(id, message) {
  const box = $(id);

  if (!box) return;

  box.textContent = message;
  box.classList.remove("hidden");
}

function clearError(id) {
  $(id)?.classList.add("hidden");
}


/* =========================================================
   CANDIDATE — JOBS
========================================================= */

async function loadCandidateJobs() {

  const grid = $("jobs");

  try {

    const data = await api("/user/jobs");

    const jobs = data.jobs || [];

    window.candidateJobs = jobs;

    $("job-count").textContent = jobs.length;

    grid.innerHTML = jobs.length
      ? jobs.map((job, index) => `

          <button
            class="card"
            style="animation-delay:${index * 70}ms"
            onclick="selectCandidateJob(${Number(job.job_id)})"
          >

            <div class="card-icon">
              ▦
            </div>

            <div class="card-body">

              <span class="eyebrow">
                Now hiring
              </span>

              <h2>
                ${escapeHtml(formatTitle(job.title))}
              </h2>

              <p>
                ${escapeHtml(job.title)}
              </p>

            </div>

            <span class="arrow">
              →
            </span>

          </button>

        `).join("")

      : `

          <div
            class="empty"
            style="grid-column:1/-1"
          >

            <h2>
              No open roles yet
            </h2>

            <p>
              There are no roles available right now.
            </p>

          </div>

        `;

  } catch (error) {

    grid.innerHTML = `

      <div
        class="error"
        style="grid-column:1/-1"
      >
        ${escapeHtml(error.message)}
      </div>

    `;

  }
}


function selectCandidateJob(jobId) {

  const job = window.candidateJobs.find(
    item => Number(item.job_id) === Number(jobId)
  );

  if (!job) return;

  sessionStorage.setItem(
    "selectedJob",
    JSON.stringify({
      job_id: Number(job.job_id),
      title: job.title
    })
  );

  sessionStorage.removeItem("uploadedResume");
  sessionStorage.removeItem("screeningResult");

  $("jobs-view").classList.add("hidden");
  $("application-view").classList.remove("hidden");

  $("selected-job-title").textContent =
    formatTitle(job.title);

  $("resume-form").classList.remove("hidden");
  $("uploaded-panel").classList.add("hidden");
  $("analysis-stage").classList.add("hidden");
  $("result-stage").classList.add("hidden");

  $("resume-form").reset();

  clearError("candidate-error");

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


function showCandidateJobs() {

  $("application-view").classList.add("hidden");
  $("jobs-view").classList.remove("hidden");

  clearError("candidate-error");

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


/* =========================================================
   CANDIDATE — UPLOAD
========================================================= */

async function uploadCandidateResume(event) {

  event.preventDefault();

  clearError("candidate-error");

  const job = JSON.parse(
    sessionStorage.getItem("selectedJob") || "null"
  );

  const file = $("resume-file").files[0];

  const name =
    $("candidate-name").value.trim();

  if (!job) {

    return showError(
      "candidate-error",
      "Please select a job first."
    );

  }

  if (!file) {

    return showError(
      "candidate-error",
      "Please select your resume PDF."
    );

  }

  if (!name) {

    return showError(
      "candidate-error",
      "Please enter your name."
    );

  }

  if (file.type !== "application/pdf") {

    return showError(
      "candidate-error",
      "Only PDF files are allowed."
    );

  }

  const button = $("upload-btn");

  button.disabled = true;

  button.innerHTML = `
    <span
      class="spinner"
      style="width:17px;height:17px;border-width:2px"
    ></span>
    Uploading...
  `;

  try {

    const form = new FormData();

    form.append(
      "candidate_name",
      name
    );

    form.append(
      "job_id",
      String(job.job_id)
    );

    form.append(
      "file",
      file
    );

    const result = await api(
      "/user/resume/upload",
      {
        method: "POST",
        body: form
      }
    );

    sessionStorage.setItem(
      "uploadedResume",
      JSON.stringify(result)
    );

    $("resume-form").classList.add("hidden");

    $("uploaded-panel").classList.remove("hidden");

    $("uploaded-name").textContent =
      result.filename;

    $("uploaded-meta").textContent =
      `Resume uploaded successfully for ${formatTitle(job.title)}`;

  } catch (error) {

    showError(
      "candidate-error",
      error.message
    );

  } finally {

    button.disabled = false;

    button.innerHTML =
      "Upload resume →";

  }
}


/* =========================================================
   CANDIDATE — SCREEN
========================================================= */

async function analyzeResume() {

  clearError("candidate-error");

  const job = JSON.parse(
    sessionStorage.getItem("selectedJob") || "null"
  );

  const uploaded = JSON.parse(
    sessionStorage.getItem("uploadedResume") || "null"
  );

  if (!job) {

    return showError(
      "candidate-error",
      "Selected job not found."
    );

  }

  if (!uploaded) {

    return showError(
      "candidate-error",
      "Please upload your resume first."
    );

  }

  $("uploaded-panel").classList.add("hidden");

  $("analysis-stage").classList.remove("hidden");

  try {

    const data = await api(
      "/user/screen-resume",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
          resume_id:
            uploaded.resume_id,

          job_id:
            job.job_id
        })
      }
    );

    sessionStorage.setItem(
      "screeningResult",
      JSON.stringify(data)
    );

    renderCandidateResult(data);

  } catch (error) {

    $("analysis-stage").classList.add("hidden");

    $("uploaded-panel").classList.remove("hidden");

    showError(
      "candidate-error",
      error.message
    );

  }
}


/* =========================================================
   CANDIDATE — RESULT HELPERS
========================================================= */

function listSection(
  title,
  items,
  mode = "bullet"
) {

  items =
    Array.isArray(items)
      ? items
      : [];

  let content;

  if (mode === "tag") {

    content = `

      <div class="items">

        ${
          items.length

            ? items.map(item => `

                <span class="tag">
                  ${escapeHtml(item)}
                </span>

              `).join("")

            : `<span class="bullet">
                 None returned.
               </span>`
        }

      </div>

    `;

  } else {

    content = `

      <div>

        ${
          items.length

            ? items.map(item => `

                <div class="bullet">

                  <b>
                    •
                  </b>

                  <span>
                    ${escapeHtml(item)}
                  </span>

                </div>

              `).join("")

            : `<span class="bullet">
                 None returned.
               </span>`
        }

      </div>

    `;
  }

  return `

    <section class="panel list reveal">

      <h2>

        ${title}

        <span class="count">
          ${items.length}
        </span>

      </h2>

      ${content}

    </section>

  `;
}


function renderCandidateResult(data) {

  $("analysis-stage").classList.add("hidden");

  $("result-stage").classList.remove("hidden");

  const result =
    data.result || {};

  $("result-job").textContent =
    `${data.candidate_name} · ${formatTitle(data.job_title)}`;

  const recommendation =
    result.recommendation ||
    "Evaluation complete";

  $("recommendation").textContent =
    recommendation;

  $("recommendation-copy").textContent =
    recommendation;

  $("summary").textContent =
    result.summary ||
    "No summary returned.";

  const score =
    result.overall_score ?? 0;

  $("score").textContent =
    score;

  $("ring").style.setProperty(
    "--angle",
    `${score * 3.6}deg`
  );

  $("details").innerHTML = [

    listSection(
      "Matched skills",
      result.matched_skills,
      "tag"
    ),

    listSection(
      "Skills to develop",
      result.missing_skills,
      "tag"
    ),

    listSection(
      "Relevant experience",
      result.relevant_experience
    ),

    listSection(
      "Strengths",
      result.strengths
    ),

    listSection(
      "Gaps to consider",
      result.gaps,
      "tag"
    )

  ].join("");

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


/* =========================================================
   RECRUITER — DASHBOARD
========================================================= */

async function loadRecruiter() {

  const area =
    $("recruiter-content");

  try {

    const data =
      await api(
        "/recruiter/jobs/resumes"
      );

    const jobs =
      data.jobs || [];

    window.recruiterJobs =
      jobs;

    $("role-count").textContent =
      jobs.length;

    $("candidate-count").textContent =
      jobs.reduce(
        (sum, job) =>
          sum +
          (job.resume_count || 0),
        0
      );

    area.innerHTML =
      jobs.length

        ? jobs.map(
            (job, index) => `

              <button
                class="card"
                style="animation-delay:${index * 70}ms"
                onclick="selectRecruiterJob(${Number(job.job_id)})"
              >

                <div class="card-icon">
                  ▦
                </div>

                <div class="card-body">

                  <span class="eyebrow">
                    Role
                  </span>

                  <h2>
                    ${escapeHtml(
                      formatTitle(job.job_title)
                    )}
                  </h2>

                  <p>

                    ${job.resume_count}

                    candidate${
                      job.resume_count === 1
                        ? ""
                        : "s"
                    }

                  </p>

                </div>

                <span class="arrow">
                  →
                </span>

              </button>

            `
          ).join("")

        : `

            <div
              class="empty"
              style="grid-column:1/-1"
            >

              <h2>
                No roles created
              </h2>

              <p>
                Upload your first job description.
              </p>

            </div>

          `;

  } catch (error) {

    area.innerHTML = `

      <div
        class="error"
        style="grid-column:1/-1"
      >

        ${escapeHtml(error.message)}

      </div>

    `;

  }
}


/* =========================================================
   RECRUITER — SELECT JOB
========================================================= */

function selectRecruiterJob(jobId) {

  const job =
    window.recruiterJobs.find(
      item =>
        Number(item.job_id) ===
        Number(jobId)
    );

  if (!job) return;

  /*
   * Remember currently selected job.
   */
  window.selectedRecruiterJobId =
    Number(jobId);

  $("recruiter-dashboard")
    .classList
    .add("hidden");

  $("recruiter-role-view")
    .classList
    .remove("hidden");

  /*
   * Reset Gmail section
   * whenever another job is opened.
   */
  resetGmailUI();

  renderRecruiterRole(job);

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


function showRecruiterDashboard() {

  $("recruiter-role-view")
    .classList
    .add("hidden");

  $("recruiter-dashboard")
    .classList
    .remove("hidden");

  window.selectedRecruiterJobId =
    null;

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}


/* =========================================================
   RECRUITER — ROLE / NORMAL CANDIDATES
========================================================= */

async function renderRecruiterRole(
  selectedJob
) {

  $("role-title-view").textContent =
    formatTitle(
      selectedJob.job_title
    );

  $("resume-count-view").textContent =
    selectedJob.resume_count || 0;

  const list =
    $("candidate-list");

  list.innerHTML = `

    <div class="loading">

      <div>

        <div class="spinner"></div>

        <p>
          Loading candidates...
        </p>

      </div>

    </div>

  `;

  try {

    const data =
      await api(
        "/recruiter/jobs/resumes"
      );

    const job =
      (data.jobs || []).find(
        item =>
          Number(item.job_id) ===
          Number(selectedJob.job_id)
      );

    if (!job) {

      list.innerHTML = `

        <div class="empty">

          <h2>
            Job not found
          </h2>

          <p>
            This job could not be found.
          </p>

        </div>

      `;

      return;
    }

    $("role-title-view").textContent =
      formatTitle(job.job_title);

    $("resume-count-view").textContent =
      job.resume_count || 0;

    const resumes =
      job.resumes || [];

    if (!resumes.length) {

      list.innerHTML = `

        <div class="empty">

          <h2>
            No candidates yet
          </h2>

          <p>
            Resumes submitted for this role
            will appear here.
          </p>

        </div>

      `;

      return;
    }

    list.innerHTML =
      resumes.map(
        (candidate, index) => {

          const screening =
            candidate.screening;

          const result =
            screening?.result || {};

          const score =
            screening?.overall_score ??
            result.overall_score ??
            null;

          const recommendation =
            screening?.recommendation ??
            result.recommendation ??
            null;

          const matchedSkills =
            result.matched_skills || [];

          return `

            <button
              type="button"
              class="candidate-row candidate-row-clickable"
              style="animation-delay:${index * 70}ms"

              onclick="
                openCandidateDetails(
                  ${Number(candidate.resume_id)},
                  ${Number(job.job_id)}
                )
              "
            >

              <div class="avatar">

                ${escapeHtml(
                  candidate.candidate_name
                    .charAt(0)
                    .toUpperCase()
                )}

              </div>

              <div class="candidate-info">

                <strong>
                  ${escapeHtml(
                    candidate.candidate_name
                  )}
                </strong>

                <span>
                  ▣
                  ${escapeHtml(
                    candidate.filename
                  )}
                </span>

                ${
                  matchedSkills.length

                    ? `

                      <div class="candidate-skills">

                        ${
                          matchedSkills
                            .slice(0, 5)
                            .map(
                              skill => `

                                <span class="tag">

                                  ${escapeHtml(
                                    skill
                                  )}

                                </span>

                              `
                            )
                            .join("")
                        }

                      </div>

                    `

                    : ""
                }

              </div>

              <div class="candidate-score">

                ${
                  score !== null

                    ? `

                      <strong>
                        ${score}
                      </strong>

                      <span>
                        /100
                      </span>

                      <small>

                        ${escapeHtml(
                          recommendation ||
                          "Screened"
                        )}

                      </small>

                    `

                    : `

                      <small>
                        Not screened
                      </small>

                    `
                }

              </div>

              <span class="candidate-open">
                →
              </span>

            </button>

          `;

        }
      ).join("");

  } catch (error) {

    list.innerHTML = `

      <div class="error">

        ${escapeHtml(
          error.message
        )}

      </div>

    `;

  }
}


/* =========================================================
   GMAIL — RESET UI
========================================================= */

function resetGmailUI() {

  const status =
    $("gmail-status");

  const results =
    $("gmail-results");

  if (status) {

    status.classList.add(
      "hidden"
    );

    status.innerHTML = "";

  }

  if (results) {

    results.classList.add(
      "hidden"
    );

    results.innerHTML = "";

  }

  const button =
    $("fetch-gmail-btn");

  if (button) {

    button.disabled = false;

    button.innerHTML =
      "Fetch from Gmail →";

  }
}


/* =========================================================
   GMAIL — FETCH + SCREEN + RANK
========================================================= */

async function fetchGmailResumes(
  jobId
) {

  clearError(
    "recruiter-error"
  );

  const button =
    $("fetch-gmail-btn");

  const status =
    $("gmail-status");

  const results =
    $("gmail-results");

  if (!button) {

    console.error(
      "Fetch Gmail button not found."
    );

    return;
  }

  button.disabled = true;

  button.innerHTML = `

    <span
      class="spinner"
      style="width:17px;height:17px;border-width:2px"
    ></span>

    Fetching...

  `;

  if (status) {

    status.classList.remove(
      "hidden"
    );

    status.innerHTML = `

      <strong>
        Connecting to Gmail...
      </strong>

      <div
        style="margin-top:5px;color:var(--muted)"
      >
        Searching for resume attachments.
      </div>

    `;

  }

  if (results) {

    results.classList.add(
      "hidden"
    );

  }

  try {

    /* =====================================================
       STEP 1 — FETCH FROM GMAIL
    ===================================================== */

    if (status) {

      status.innerHTML = `

        <strong>
          Fetching resumes from Gmail...
        </strong>

        <div
          style="margin-top:5px;color:var(--muted)"
        >
          Please wait while TalentFlow reads
          the resume attachments.
        </div>

      `;

    }

    const fetchData =
      await api(
        `/recruiter/jobs/${jobId}/gmail/fetch-resumes`,
        {
          method: "POST"
        }
      );

    const savedCount =
      fetchData.saved_count || 0;

    const skippedCount =
      fetchData.skipped_count || 0;

    if (status) {

      status.innerHTML = `

        <strong>
          ✓ Gmail resumes fetched
        </strong>

        <div
          style="margin-top:5px;color:var(--muted)"
        >

          ${savedCount}
          new resume${
            savedCount === 1
              ? ""
              : "s"
          }

          found.

          ${
            skippedCount
              ? `
                ${skippedCount}
                already imported.
              `
              : ""
          }

        </div>

      `;

    }


    /* =====================================================
       STEP 2 — SCREEN ALL GMAIL RESUMES
    ===================================================== */

    if (status) {

      status.innerHTML += `

        <div
          style="margin-top:12px"
        >

          <strong>
            AI screening in progress...
          </strong>

          <div
            style="margin-top:5px;color:var(--muted)"
          >
            Comparing resumes with the
            ${escapeHtml(
              $("role-title-view").textContent
            )} job description.
          </div>

        </div>

      `;

    }

    await api(
      `/recruiter/jobs/${jobId}/gmail/screen`,
      {
        method: "POST"
      }
    );


    /* =====================================================
       STEP 3 — GET TOP / RANKED CANDIDATES
    ===================================================== */

    if (status) {

      status.innerHTML += `

        <div
          style="margin-top:12px"
        >

          <strong>
            Ranking candidates...
          </strong>

        </div>

      `;

    }

    const topData =
      await api(
        `/recruiter/jobs/${jobId}/gmail/top-resumes?limit=10`
      );


    /* =====================================================
       STEP 4 — DISPLAY RESULTS
    ===================================================== */

    renderGmailResults(
      topData
    );

    if (status) {

      status.innerHTML = `

        <strong>
          ✓ Gmail screening complete
        </strong>

        <div
          style="margin-top:5px;color:var(--muted)"
        >

          ${
            topData.candidate_count || 0
          }

          candidate${
            topData.candidate_count === 1
              ? ""
              : "s"
          }

          ranked for this role.

        </div>

      `;

    }


    /* =====================================================
       STEP 5 — REFRESH NORMAL CANDIDATE COUNT
    ===================================================== */

    try {

      const roleData =
        await api(
          "/recruiter/jobs/resumes"
        );

      const updatedJob =
        (roleData.jobs || []).find(
          item =>
            Number(item.job_id) ===
            Number(jobId)
        );

      if (updatedJob) {

        $("resume-count-view")
          .textContent =
          updatedJob.resume_count || 0;

      }

    } catch (refreshError) {

      console.warn(
        "Could not refresh candidate count:",
        refreshError
      );

    }

  } catch (error) {

    console.error(
      "Gmail workflow failed:",
      error
    );

    if (status) {

      status.classList.remove(
        "hidden"
      );

      status.innerHTML = `

        <strong>
          Gmail screening failed
        </strong>

        <div
          style="margin-top:5px"
        >
          ${escapeHtml(
            error.message
          )}
        </div>

      `;

    }

  } finally {

    button.disabled = false;

    button.innerHTML =
      "Fetch from Gmail →";

  }
}


/* =========================================================
   GMAIL — DISPLAY RANKED CANDIDATES
========================================================= */

function renderGmailResults(
  data
) {

  const container =
    $("gmail-results");

  if (!container) return;

  const candidates =
    data.candidates || [];

  if (!candidates.length) {

    container.innerHTML = `

      <div class="empty">

        <h2>
          No screened Gmail candidates
        </h2>

        <p>
          No resume candidates were available
          for this role.
        </p>

      </div>

    `;

    container.classList.remove(
      "hidden"
    );

    return;
  }

  container.innerHTML = `

    <div
      style="margin-bottom:12px"
    >

      <p class="eyebrow">
        Ranked Gmail candidates
      </p>

      <h2 style="margin:0">
        Top ${candidates.length} candidates
      </h2>

    </div>

    <div class="gmail-results">

      ${
        candidates.map(
          (candidate, index) => {

            const result =
              candidate.result || {};

            const matchedSkills =
              result.matched_skills || [];

            return `

              <div
                class="gmail-result-row"
              >

                <div class="gmail-rank">
                  ${index + 1}
                </div>


                <div
                  class="gmail-candidate-info"
                >

                  <strong>

                    ${escapeHtml(
                      candidate.candidate_name ||
                      "Unknown candidate"
                    )}

                  </strong>

                  <span>

                    ▣

                    ${escapeHtml(
                      candidate.filename || ""
                    )}

                  </span>

                  ${
                    candidate.email_address
                      ? `

                        <span>
                          ✉
                          ${escapeHtml(
                            candidate.email_address
                          )}
                        </span>

                      `
                      : ""
                  }


                  ${
                    matchedSkills.length

                      ? `

                        <div
                          class="candidate-skills"
                        >

                          ${
                            matchedSkills
                              .slice(0, 5)
                              .map(
                                skill => `

                                  <span
                                    class="tag"
                                  >

                                    ${escapeHtml(
                                      skill
                                    )}

                                  </span>

                                `
                              )
                              .join("")
                          }

                        </div>

                      `

                      : ""
                  }

                </div>


                <div
                  class="gmail-score"
                >

                  <strong>
                    ${
                      candidate.overall_score ??
                      "—"
                    }
                  </strong>

                  <span>
                    /100
                  </span>

                  <small
                    style="
                      display:block;
                      margin-top:3px;
                      color:var(--muted);
                      font-size:10px;
                    "
                  >

                    ${escapeHtml(
                      candidate.recommendation ||
                      "Screened"
                    )}

                  </small>

                </div>

              </div>

            `;

          }
        ).join("")
      }

    </div>

  `;

  container.classList.remove(
    "hidden"
  );
}


/* =========================================================
   RECRUITER — CANDIDATE DETAILS
========================================================= */

async function openCandidateDetails(
  resumeId,
  jobId
) {

  try {

    const data =
      await api(
        "/recruiter/jobs/resumes"
      );

    const job =
      (data.jobs || []).find(
        item =>
          Number(item.job_id) ===
          Number(jobId)
      );

    const candidate =
      job?.resumes?.find(
        item =>
          Number(item.resume_id) ===
          Number(resumeId)
      );

    if (!candidate) {

      throw new Error(
        "Candidate details not found."
      );

    }

    showCandidateDetails(
      candidate,
      job
    );

  } catch (error) {

    alert(
      error.message
    );

  }
}


function showCandidateDetails(
  candidate,
  job
) {

  const screening =
    candidate.screening;

  const result =
    screening?.result || {};

  const score =
    screening?.overall_score ??
    result.overall_score ??
    null;

  const recommendation =
    screening?.recommendation ??
    result.recommendation ??
    "Not screened";

  const modal =
    document.createElement("div");

  modal.id =
    "candidate-modal";

  modal.className =
    "candidate-modal";

  modal.innerHTML = `

    <div
      class="candidate-modal-backdrop"
      onclick="closeCandidateDetails()"
    ></div>


    <div
      class="candidate-modal-panel"
    >

      <button
        type="button"
        class="modal-close"
        onclick="closeCandidateDetails()"
        aria-label="Close"
      >
        ×
      </button>


      <div
        class="modal-header"
      >

        <div class="modal-avatar">

          ${escapeHtml(
            candidate.candidate_name
              .charAt(0)
              .toUpperCase()
          )}

        </div>


        <div>

          <p class="eyebrow">
            Candidate screening
          </p>

          <h2>

            ${escapeHtml(
              candidate.candidate_name
            )}

          </h2>

          <p class="modal-file">

            ▣

            ${escapeHtml(
              candidate.filename
            )}

          </p>

          <p class="modal-role">

            ${escapeHtml(
              formatTitle(
                job.job_title
              )
            )}

          </p>

        </div>


        <div class="modal-score">

          ${
            score !== null

              ? `

                <strong>
                  ${score}
                </strong>

                <span>
                  /100
                </span>

                <small>
                  ${escapeHtml(
                    recommendation
                  )}
                </small>

              `

              : `

                <strong>
                  —
                </strong>

                <small>
                  Not screened
                </small>

              `
          }

        </div>

      </div>


      ${
        screening

          ? `

            <div
              class="modal-recommendation"
            >

              <span>
                Recommendation
              </span>

              <strong>
                ${escapeHtml(
                  recommendation
                )}
              </strong>

            </div>


            <section
              class="modal-section modal-summary"
            >

              <p
                class="modal-section-label"
              >
                AI Summary
              </p>

              <p>

                ${escapeHtml(
                  result.summary ||
                  "No summary returned."
                )}

              </p>

            </section>


            <div
              class="modal-detail-grid"
            >

              <section
                class="modal-section"
              >

                <h3>
                  Matched Skills
                </h3>

                <div
                  class="modal-tags"
                >

                  ${
                    (
                      result.matched_skills ||
                      []
                    )
                    .map(
                      skill => `

                        <span
                          class="modal-tag"
                        >
                          ${escapeHtml(
                            skill
                          )}
                        </span>

                      `
                    )
                    .join("")
                  }

                </div>

              </section>


              <section
                class="modal-section"
              >

                <h3>
                  Missing Skills
                </h3>

                <div
                  class="modal-tags"
                >

                  ${
                    (
                      result.missing_skills ||
                      []
                    )
                    .map(
                      skill => `

                        <span
                          class="modal-tag missing"
                        >
                          ${escapeHtml(
                            skill
                          )}
                        </span>

                      `
                    )
                    .join("")
                  }

                </div>

              </section>


              <section
                class="modal-section"
              >

                <h3>
                  Relevant Experience
                </h3>

                <div
                  class="modal-bullets"
                >

                  ${
                    (
                      result.relevant_experience ||
                      []
                    )
                    .map(
                      item => `

                        <div>

                          <span>
                            •
                          </span>

                          <p>
                            ${escapeHtml(
                              item
                            )}
                          </p>

                        </div>

                      `
                    )
                    .join("")
                  }

                </div>

              </section>


              <section
                class="modal-section"
              >

                <h3>
                  Strengths
                </h3>

                <div
                  class="modal-bullets"
                >

                  ${
                    (
                      result.strengths ||
                      []
                    )
                    .map(
                      item => `

                        <div>

                          <span>
                            •
                          </span>

                          <p>
                            ${escapeHtml(
                              item
                            )}
                          </p>

                        </div>

                      `
                    )
                    .join("")
                  }

                </div>

              </section>


              <section
                class="modal-section"
              >

                <h3>
                  Gaps
                </h3>

                <div
                  class="modal-bullets"
                >

                  ${
                    (
                      result.gaps ||
                      []
                    )
                    .map(
                      item => `

                        <div>

                          <span>
                            •
                          </span>

                          <p>
                            ${escapeHtml(
                              item
                            )}
                          </p>

                        </div>

                      `
                    )
                    .join("")
                  }

                </div>

              </section>

            </div>

          `

          : `

            <div
              class="modal-not-screened"
            >

              <h3>
                Resume not screened yet
              </h3>

              <p>
                This candidate has uploaded a
                resume for this role, but no AI
                screening result is available yet.
              </p>

            </div>

          `
      }

    </div>

  `;

  document.body.appendChild(
    modal
  );

  document.body.classList.add(
    "modal-open"
  );

  requestAnimationFrame(() => {

    modal.classList.add(
      "show"
    );

  });
}


function closeCandidateDetails() {

  const modal =
    document.getElementById(
      "candidate-modal"
    );

  if (!modal) return;

  modal.classList.remove(
    "show"
  );

  setTimeout(() => {

    modal.remove();

    document.body.classList.remove(
      "modal-open"
    );

  }, 220);
}


document.addEventListener(
  "keydown",
  event => {

    if (
      event.key === "Escape"
    ) {

      closeCandidateDetails();

    }

  }
);


/* =========================================================
   RECRUITER — CREATE JOB
========================================================= */

async function createJob(event) {

  event.preventDefault();

  clearError(
    "recruiter-error"
  );

  const title =
    $("job-title")
      .value
      .trim();

  const file =
    $("job-file")
      .files[0];

  if (!title || !file) {

    return showError(
      "recruiter-error",
      "Enter a role title and choose a PDF."
    );

  }

  if (
    file.type !==
    "application/pdf"
  ) {

    return showError(
      "recruiter-error",
      "Only PDF job descriptions are allowed."
    );

  }

  const button =
    $("create-btn");

  button.disabled = true;

  button.innerHTML =
    "Uploading...";

  try {

    const form =
      new FormData();

    form.append(
      "title",
      title
    );

    form.append(
      "file",
      file
    );

    await api(
      "/recruiter/job-description/upload",
      {
        method: "POST",
        body: form
      }
    );

    $("create-job-form")
      .reset();

    $("create-area")
      .classList
      .add("hidden");

    await loadRecruiter();

  } catch (error) {

    showError(
      "recruiter-error",
      error.message
    );

  } finally {

    button.disabled = false;

    button.innerHTML =
      "Create role →";

  }
}


/* =========================================================
   INITIALIZATION
========================================================= */

document.addEventListener(
  "DOMContentLoaded",
  async () => {

    /* =====================================================
       CANDIDATE PAGE
    ===================================================== */

    if ($("jobs")) {

      await loadCandidateJobs();

    }


    /* =====================================================
       CANDIDATE EVENTS
    ===================================================== */

    $("back-to-jobs")
      ?.addEventListener(
        "click",
        event => {

          event.preventDefault();

          showCandidateJobs();

        }
      );


    $("resume-form")
      ?.addEventListener(
        "submit",
        uploadCandidateResume
      );


    $("analyze-btn")
      ?.addEventListener(
        "click",
        analyzeResume
      );


    /* =====================================================
       RECRUITER PAGE
    ===================================================== */

    if ($("recruiter-content")) {

      await loadRecruiter();

    }


    /* =====================================================
       CREATE JOB
    ===================================================== */

    $("show-create-btn")
      ?.addEventListener(
        "click",
        () => {

          $("create-area")
            .classList
            .toggle("hidden");

        }
      );


    $("create-job-form")
      ?.addEventListener(
        "submit",
        createJob
      );


    /* =====================================================
       BACK TO RECRUITER
    ===================================================== */

    $("back-to-recruiter")
      ?.addEventListener(
        "click",
        event => {

          event.preventDefault();

          showRecruiterDashboard();

        }
      );


    /* =====================================================
       GMAIL FETCH BUTTON
    ===================================================== */

    $("fetch-gmail-btn")
      ?.addEventListener(
        "click",
        () => {

          const jobId =
            window.selectedRecruiterJobId;

          if (!jobId) {

            return showError(
              "recruiter-error",
              "Please select a job first."
            );

          }

          fetchGmailResumes(
            jobId
          );

        }
      );

  }
);