/* ClipLingo feed: vertical snap-scroll cards, one audio clip + quiz each.
 * The visible card's clip auto-plays; scrolling away pauses it. */

const feed = document.getElementById("feed");
const template = document.getElementById("card-template");
const overlay = document.getElementById("start-overlay");
const onboarding = document.getElementById("onboarding");
const topicChipsEl = document.getElementById("topic-chips");
const levelCardsEl = document.getElementById("level-cards");
const saveBtn = document.getElementById("prefs-save");
const gearBtn = document.getElementById("edit-prefs");
const emptyState = document.getElementById("empty-state");
let started = false;
let allClips = [];
let menuTopics = [];

const PREFS_KEY = "cliplingo.prefs";
const LEVELS = ["beginner", "intermediate", "advanced"];
const LEVEL_HINTS = {
  beginner: "Slow & simple",
  intermediate: "Everyday pace",
  advanced: "Fast & rich",
};
const FEED_CAP = 20;

async function loadFeed() {
  let manifest;
  try {
    const res = await fetch("data/manifest.json");
    manifest = await res.json();
  } catch {
    overlay.querySelector("p").textContent =
      "No feed found. Run `python -m pipeline demo` first, then refresh.";
    document.getElementById("start-btn").hidden = true;
    return;
  }
  allClips = manifest.clips || [];
  menuTopics = topicMenu(manifest);
  if (!menuTopics.length) {
    renderFeed(shuffle(allClips)); // legacy manifest: show everything
    return;
  }
  gearBtn.hidden = false;
  const prefs = loadPrefs();
  if (!prefs) {
    showOnboarding(menuTopics, { topics: [], level: null });
  } else {
    renderFeed(filterClips(allClips, prefs));
  }
}

/* Menu from manifest meta; fall back to topics present on clips. */
function topicMenu(manifest) {
  if (Array.isArray(manifest.topics) && manifest.topics.length) return manifest.topics;
  const keys = [...new Set((manifest.clips || []).map((c) => c.topic).filter(Boolean))];
  return keys.map((key) => ({ key, label: key[0].toUpperCase() + key.slice(1) }));
}

function loadPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PREFS_KEY));
    if (p && Array.isArray(p.topics) && p.topics.length && LEVELS.includes(p.level)) return p;
  } catch {}
  return null;
}

/* Feed composition (spec): candidates -> primary level pool -> top up from
 * adjacent levels nearest-first (lower level first on ties) until the cap ->
 * shuffle -> cap. Unrated (null difficulty) clips never enter a leveled feed. */
function filterClips(clips, prefs) {
  const levelIdx = LEVELS.indexOf(prefs.level);
  const candidates = clips.filter(
    (c) => prefs.topics.includes(c.topic) && LEVELS.includes(c.difficulty)
  );
  const picked = candidates.filter((c) => c.difficulty === prefs.level);
  if (picked.length < FEED_CAP) {
    const fallbackOrder = LEVELS.map((lvl, i) => ({ lvl, dist: Math.abs(i - levelIdx), i }))
      .filter((o) => o.dist > 0)
      .sort((a, b) => a.dist - b.dist || a.i - b.i)
      .map((o) => o.lvl);
    for (const lvl of fallbackOrder) {
      for (const c of candidates) {
        if (picked.length >= FEED_CAP) break;
        if (c.difficulty === lvl) picked.push(c);
      }
    }
  }
  return shuffle(picked).slice(0, FEED_CAP);
}

function renderFeed(clips) {
  feed.querySelectorAll(".card").forEach((c) => c.remove());
  emptyState.hidden = clips.length > 0;
  clips.forEach((clip) => feed.appendChild(buildCard(clip)));
  observeCards();
  if (started) {
    const first = feed.querySelector(".card audio");
    if (first) first.play().catch(() => {});
  }
}

function showOnboarding(topics, current) {
  // Ignore saved topics that are not in today's menu — a stale key would
  // otherwise invisibly satisfy the "≥1 topic" gate with no chip selected.
  const menuKeys = new Set(topics.map((t) => t.key));
  const selected = new Set(current.topics.filter((k) => menuKeys.has(k)));
  let level = current.level;

  topicChipsEl.replaceChildren();
  topics.forEach((t) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (selected.has(t.key) ? " selected" : "");
    chip.textContent = t.label;
    chip.addEventListener("click", () => {
      selected.has(t.key) ? selected.delete(t.key) : selected.add(t.key);
      chip.classList.toggle("selected", selected.has(t.key));
      updateSave();
    });
    topicChipsEl.appendChild(chip);
  });

  levelCardsEl.replaceChildren();
  LEVELS.forEach((lvl) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "level-card" + (lvl === level ? " selected" : "");
    card.innerHTML = `<strong>${lvl[0].toUpperCase() + lvl.slice(1)}</strong><span>${LEVEL_HINTS[lvl]}</span>`;
    card.addEventListener("click", () => {
      level = lvl;
      [...levelCardsEl.children].forEach((el) => el.classList.remove("selected"));
      card.classList.add("selected");
      updateSave();
    });
    levelCardsEl.appendChild(card);
  });

  function updateSave() {
    saveBtn.disabled = !(selected.size > 0 && level);
  }
  updateSave();

  saveBtn.onclick = () => {
    const prefs = { topics: [...selected], level };
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    onboarding.hidden = true;
    renderFeed(filterClips(allClips, prefs));
  };
  onboarding.hidden = false;
}

gearBtn.addEventListener("click", () => {
  showOnboarding(menuTopics, loadPrefs() || { topics: [], level: null });
});

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function buildCard(clip) {
  const node = template.content.firstElementChild.cloneNode(true);
  const audio = node.querySelector("audio");
  audio.src = clip.audio;

  const badge = node.querySelector(".badge");
  badge.textContent = clip.source;
  badge.dataset.source = clip.source;

  const attr = node.querySelector(".attribution");
  if (clip.url) attr.href = clip.url; else attr.hidden = true;

  node.querySelector(".clip-title").textContent =
    `${clip.title}${clip.uploader ? " — " + clip.uploader : ""} · ${clip.duration}s`;

  // quiz
  const quiz = node.querySelector(".quiz");
  const promptEl = node.querySelector(".prompt");
  const optionsEl = node.querySelector(".options");
  const feedbackEl = node.querySelector(".feedback");
  if (clip.question) {
    promptEl.textContent = clip.question.prompt;
    clip.question.options.forEach((opt, i) => {
      const btn = document.createElement("button");
      btn.textContent = opt;
      btn.addEventListener("click", () => {
        const correct = i === clip.question.answer_index;
        btn.classList.add(correct ? "correct" : "wrong");
        optionsEl.children[clip.question.answer_index].classList.add("correct");
        [...optionsEl.children].forEach((b) => (b.disabled = true));
        feedbackEl.textContent = correct ? "Nice — that's it!" : "Not quite. Listen again?";
        feedbackEl.className = "feedback " + (correct ? "good" : "bad");
      });
      optionsEl.appendChild(btn);
    });
  } else {
    quiz.classList.add("no-question");
    promptEl.textContent = "No transcript for this clip — just listen and repeat out loud.";
  }

  // transcript reveal
  const transcriptEl = node.querySelector(".transcript");
  const revealBtn = node.querySelector(".reveal");
  if (clip.transcript) {
    transcriptEl.textContent = clip.transcript;
    revealBtn.addEventListener("click", () => {
      transcriptEl.hidden = !transcriptEl.hidden;
      revealBtn.textContent = transcriptEl.hidden ? "Show transcript" : "Hide transcript";
    });
  } else {
    revealBtn.disabled = true;
  }

  // playback controls
  const playBtn = node.querySelector(".play-toggle");
  playBtn.addEventListener("click", () => {
    if (audio.paused) audio.play(); else audio.pause();
  });
  node.querySelector(".replay").addEventListener("click", () => {
    audio.currentTime = 0;
    audio.play();
  });
  audio.addEventListener("play", () => node.classList.add("playing"));
  audio.addEventListener("pause", () => node.classList.remove("playing"));
  audio.addEventListener("ended", () => node.classList.remove("playing"));
  const fill = node.querySelector(".progress-fill");
  audio.addEventListener("timeupdate", () => {
    if (audio.duration) fill.style.width = (audio.currentTime / audio.duration) * 100 + "%";
  });
  return node;
}

function observeCards() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const audio = entry.target.querySelector("audio");
        if (entry.isIntersecting && entry.intersectionRatio > 0.6) {
          if (started) audio.play().catch(() => {});
        } else {
          audio.pause();
        }
      });
    },
    { root: feed, threshold: [0.6] }
  );
  document.querySelectorAll(".card").forEach((c) => observer.observe(c));
}

document.getElementById("start-btn").addEventListener("click", () => {
  started = true;
  overlay.classList.add("hidden");
  const first = feed.querySelector(".card audio");
  if (first) first.play().catch(() => {});
});

loadFeed();
