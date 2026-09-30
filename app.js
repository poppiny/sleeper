import { FORMS, STAGES, NEXT, HEARTS, GRACE, EARLY, MIN, HOUR, newState, tick, sleep, wake, canLeave, leave, streak, dayKey } from './game.js';

const KEY = 'sleeper.v1';
const $ = s => document.querySelector(s);
const dlg = $('#dlg');
let st = load();
let waking = false;

function load() {
  try { const s = JSON.parse(localStorage.getItem(KEY)); if (s?.pet) return s; } catch {}
  return newState(Date.now());
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch {} }

const sprite = (form, asleep) => `assets/${form}${asleep && form !== 'egg' ? '_sleep' : ''}.png`;
const fmt = m => { m = Math.max(0, Math.ceil(m)); const h = Math.floor(m / 60); return h ? `${h}時間${m % 60 ? `${m % 60}分` : ''}` : `${m}分`; };
const clock = ms => { const s = Math.floor(ms / 1000); return `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };
const time = t => { const d = new Date(t); return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`; };
const isNight = t => { const h = new Date(t).getHours(); return h >= 20 || h < 6; };
const esc = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
const wait = ms => new Promise(r => setTimeout(r, ms));
const preload = src => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = src; });
const setSrc = (img, src) => { if (img.getAttribute('src') !== src) img.src = src; };
const HEART = 'M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z'; // 7x6 pixel heart
const stars = f => f.rare ? `<em class="rare">${'★'.repeat(f.rare)}${f.rare > 1 ? 'でんせつ' : 'レア'}</em>` : '';

const TALK = {
  egg: ['……ことこと', '（ほんのり あたたかい）', '……すぴー'],
  zero: ['ぐったり…', 'ねかせて…', 'もう げんきが でない…'],
  tired: ['ねむい…', 'ちょっと 休ませて…', 'スマホ おいて…？'],
  normal: ['いっしょに ひとやすみ しよ', 'スマホ おいてくれたら うれしいな', 'きょうも がんばったね', 'ふわぁ…', 'なでてくれた！', 'おやすみの じかん まだ？'],
};

function render() {
  const now = Date.now(), p = st.pet, f = FORMS[p.form], s = f.stage, night = isNight(now);
  document.body.classList.toggle('night', night);
  setSrc($('#bg'), `assets/bg_${night ? 'night' : 'day'}.png`);
  setSrc($('#pet'), sprite(p.form));
  $('#petWrap').className = `pet s${s}${p.shiny && s ? ' shiny' : ''}${s && !p.energy ? ' tired' : ''}`;
  $('#name').textContent = p.name;
  $('#age').textContent = `${Math.floor((now - p.born) / 864e5) + 1}日目`;
  $('#stage').innerHTML = `${STAGES[s]}${s ? `・${f.name}` : ''}${stars(f)}${p.shiny && s ? ' ✨' : ''}`;
  $('#hearts').innerHTML = s ? Array.from({ length: HEARTS }, (_, i) => `<svg viewBox="0 0 7 6" class="${i < Math.ceil(p.energy) ? 'on' : ''}"><path d="${HEART}"/></svg>`).join('') : '';
  const lo = s ? NEXT[s - 1] : 0, hi = NEXT[s];
  $('#barFill').style.width = `${Math.min(1, (p.xp - lo) / (hi - lo)) * 100}%`;
  $('#goal').textContent = !s ? `あと ${fmt(hi - p.xp)} スマホを置くと うまれるよ`
    : s < 3 ? `つぎの成長まで あと ${fmt(hi - p.xp)}`
    : canLeave(p) ? 'たびだちの じゅんびが できたみたい' : `たびだちまで あと ${fmt(hi - p.xp)}`;
  $('#alert').hidden = p.zero == null;
  if (p.zero != null) $('#alert').textContent = `ぐったりしてる！ おやすみさせてあげて（いえでまで あと ${fmt((p.zero + 72 * HOUR - now) / MIN)}）`;
  $('#leaveBtn').hidden = !canLeave(p);
  $('#today').textContent = fmt(st.days[dayKey(now)] || 0);
  $('#streak').textContent = `${streak(st, now)}日`;

  $('#sleepView').hidden = !st.sleep;
  if (!st.sleep) return;
  const el = now - st.sleep.start;
  $('#timer').textContent = clock(el);
  setSrc($('#sleepImg'), sprite(p.form, true));
  $('#sleepImg').className = p.shiny && s ? 'shiny' : '';
  $('#wakeBtn').textContent = el < GRACE ? 'やめる' : 'おこす';
  $('#sleepHint').innerHTML = el < GRACE ? 'スマホを ふせて置いてね<br>画面を消しても だいじょうぶ'
    : el < EARLY * MIN ? (s ? 'ねむりかけ…<br>5分たつまえに 起こすと おせわミス' : 'たまごを あたためているよ')
    : 'すやすや…<br>つぎに アプリを開くと 目をさますよ';
}

function loop() {
  if (document.hidden) return;
  const ran = tick(st, Date.now());
  if (ran) { save(); show(`<h2>いえで…</h2><img class="big" src="${sprite(ran.form)}" alt=""><p>${esc(ran.name)}は げんきが なくなって いえでして しまった…</p><p class="note">あたらしい たまごが とどいたよ。こんどは スマホを置いて やすませてあげてね。</p>`); }
  render();
}

function show(html) {
  if (dlg.open) dlg.close();
  $('#dlgBody').innerHTML = html;
  dlg.showModal();
  return new Promise(r => dlg.addEventListener('close', r, { once: true }));
}

async function wakeUp() {
  if (!st.sleep || waking) return;
  waking = true;
  const before = st.pet.form, r = wake(st, Date.now());
  save(); render();
  if (r.kind === 'early') {
    await show(`<h2>おこしちゃった…</h2><img class="big" src="${sprite(before)}" alt=""><p>${r.min}分で 目が さめちゃった。</p>` +
      (before === 'egg' ? '<p class="note">たまごは もっと ながく あたためてね。</p>' : '<p class="warn">5分たつまえに 起こすと おせわミス！</p>'));
  } else if (r.kind === 'ok') {
    await show(`<h2>${r.min >= 360 ? 'ぐっすり！' : 'おはよう！'}</h2><img class="big" src="${sprite(before, true)}" alt="">
      <p><b>${fmt(r.min)}</b> スマホを置いていたよ</p>
      <p class="gain">そだち +${r.min}${before !== 'egg' ? '　げんき かいふく' : ''}</p>
      ${r.evolved.length ? '<p class="warn">…おや？ ようすが…！</p>' : ''}`);
    for (const e of r.evolved) await evolution(e.from, e.to);
  }
  waking = false;
}

async function evolution(from, to) {
  const box = $('#evo'), img = $('#evoImg'), text = $('#evoText'), ok = $('#evoOk'), f = FORMS[to], hatch = from === 'egg';
  await Promise.all([preload(sprite(from)), preload(sprite(to))]);
  box.hidden = false; box.classList.remove('done'); ok.hidden = true; img.className = 'sil';
  text.textContent = hatch ? 'たまごが…！？' : `おや…？ ${st.pet.name}の ようすが…！`;
  for (let i = 0, d = 450; i < 16; i++, d = Math.max(70, d * 0.8)) { img.src = sprite(i % 2 ? to : from); await wait(d); }
  img.src = sprite(to); img.className = st.pet.shiny ? 'shiny' : ''; box.classList.add('done');
  text.innerHTML = `${f.name}${hatch ? ' が うまれた！' : ' に しんか した！'}${stars(f)}${st.pet.shiny ? '<br>✨ いろちがい！ ✨' : ''}`;
  ok.hidden = false;
  await new Promise(r => { ok.onclick = r; });
  box.hidden = true;
}

function help() {
  return show(`<h2>あそびかた</h2><ol class="help">
    <li><b>おやすみ</b>を おしたら、スマホを ふせて置こう。画面を消してOK。</li>
    <li>つぎに アプリを開くと 目をさまして、スマホを置いていた時間だけ 育つよ。</li>
    <li>たまごは 20分で うまれる。あかちゃん → こども → おとなへ しんか！</li>
    <li><b>げんき</b>は 起きている間に へっていく。0になったり、5分たつまえに 起こしたりすると <b>おせわミス</b>。</li>
    <li>夜か昼か・ミスの数・どれだけ長く ねかせたかで しんか先が かわる。★レアや でんせつの子も…！</li>
    <li>げんき0のまま 3日たつと いえでしちゃう。</li>
    <li>おとなになって そだち40時間で たびだち。つぎの たまごが とどくよ。</li>
  </ol><p class="note">※ ほかのアプリを 使っていても 見分けられません。正直に あそんでね。</p>`);
}

function log() {
  const now = Date.now(), p = st.pet;
  const week = Array.from({ length: 7 }, (_, i) => { const d = new Date(now); d.setDate(d.getDate() - 6 + i); return [d, st.days[dayKey(d)] || 0]; });
  const max = Math.max(60, ...week.map(w => w[1]));
  show(`<h2>きろく</h2>
    <div class="stats">
      <div><small>この子の そだち</small><b>${fmt(p.xp)}</b></div>
      <div><small>おせわミス</small><b>${p.lifeMiss}回</b></div>
      <div><small>さいちょう</small><b>${fmt(st.best)}</b></div>
      <div><small>ぜんぶで</small><b>${fmt(st.total)}</b></div>
    </div>
    <h3>さいきん 7日</h3>
    <div class="week">${week.map(([d, m]) => `<div><i style="height:${m / max * 80}%"></i><small>${d.getMonth() + 1}/${d.getDate()}</small></div>`).join('')}</div>
    <h3>おやすみ りれき</h3>
    <ul class="history">${st.log.slice(0, 10).map(l => `<li><span>${time(l.s)} → ${time(l.e)}</span><b>${fmt(l.min)}</b></li>`).join('') || '<li>まだ ないよ</li>'}</ul>
    <h3>アルバム</h3>
    ${st.album.length ? `<div class="album">${st.album.map(a => `<figure><img src="${sprite(a.form)}" class="${a.shiny ? 'shiny' : ''}" alt=""><figcaption>${esc(a.name)}<br><small>${FORMS[a.form].name}</small></figcaption></figure>`).join('')}</div>`
      : '<p class="note">おとなになって たびだった子が ここに のこるよ</p>'}`);
}

function dex() {
  const ids = Object.keys(FORMS);
  show(`<h2>ずかん <small>${ids.filter(id => st.dex[id]).length} / ${ids.length}</small></h2>
    <div class="dex">${ids.map(id => {
      const f = FORMS[id], d = st.dex[id] || 0;
      return `<button type="button" data-id="${id}" class="${d ? '' : 'unknown'}"><img src="${sprite(id)}" class="${d === 2 ? 'shiny' : ''}" alt="">
        <span>${d ? f.name : '？？？'}</span>${f.rare ? `<em class="rare">${'★'.repeat(f.rare)}</em>` : ''}${d & 2 ? '<em class="shine">✨</em>' : ''}</button>`;
    }).join('')}</div>
    <p id="dexInfo" class="dex-info">タップすると せつめいが 見られるよ</p>`);
  $('#dlgBody .dex').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    const f = FORMS[b.dataset.id];
    $('#dexInfo').innerHTML = st.dex[b.dataset.id] ? `<b>${f.name}</b>（${STAGES[f.stage]}）<br>${f.desc}` : `<b>？？？</b><br>ヒント：${f.hint}`;
  };
}

$('#sleepBtn').onclick = () => { sleep(st, Date.now()); save(); render(); navigator.storage?.persist?.(); };
$('#wakeBtn').onclick = wakeUp;
$('#helpBtn').onclick = help;
$('#logBtn').onclick = log;
$('#dexBtn').onclick = dex;
$('#name').onclick = () => {
  const n = prompt('なまえを つけてね', st.pet.name)?.trim();
  if (n) { st.pet.name = n.slice(0, 10); save(); render(); }
};
$('#pet').onclick = e => {
  const p = st.pet, img = e.currentTarget;
  img.classList.remove('hop'); void img.offsetWidth; img.classList.add('hop');
  const lines = !FORMS[p.form].stage ? TALK.egg : !p.energy ? TALK.zero : p.energy < 1.5 ? TALK.tired : TALK.normal;
  const b = $('#bubble');
  b.textContent = lines[Math.floor(Math.random() * lines.length)]; b.hidden = false;
  clearTimeout(b.t); b.t = setTimeout(() => { b.hidden = true; }, 2500);
};
$('#leaveBtn').onclick = () => {
  const p = st.pet;
  if (!confirm(`${p.name}を たびだたせますか？\nきろくの アルバムに のこります。`)) return;
  leave(st, Date.now()); save(); render();
  show(`<h2>いってらっしゃい！</h2><img class="big${p.shiny ? ' shiny' : ''}" src="${sprite(p.form)}" alt=""><p>${esc(p.name)}は げんきに たびだって いった。</p><p class="note">あたらしい たまごが とどいたよ。</p>`);
};
document.addEventListener('visibilitychange', () => {
  if (document.hidden) save();
  else if (st.sleep) wakeUp(); // coming back to the app = the phone was touched
  else loop();
});

$('#install').hidden = navigator.standalone !== false;
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
if (st.sleep) wakeUp();
else if (!st.helped) { st.helped = 1; save(); help(); }
loop();
setInterval(loop, 1000);
