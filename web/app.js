/* ClipLingo feed: vertical snap-scroll cards, one audio clip + quiz each.
 * The visible card's clip auto-plays; scrolling away pauses it. */

const feed = document.getElementById("feed");
const template = document.getElementById("card-template");
const overlay = document.getElementById("start-overlay");
let started = false;

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
  const clips = shuffle(manifest.clips || []);
  clips.forEach((clip) => feed.appendChild(buildCard(clip)));
  observeCards();
}

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
