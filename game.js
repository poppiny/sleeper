// Game rules. Pure state functions (no DOM) so test.mjs can run them in Node.
export const MIN = 60e3, HOUR = 60 * MIN;
export const GRACE = 15e3;          // time to put the phone down; waking before this just cancels
export const EARLY = 5;             // minutes; waking before this is an おせわミス
export const MAX_SESSION = 12 * 60; // minutes credited per session at most (phone forgotten on a desk)
export const DECAY = 5 * HOUR;      // one heart lost per 5 awake hours
export const HEARTS = 4;
export const NEXT = [20, 180, 900, 2400]; // cumulative quiet minutes: hatch, child, adult, ready to leave
export const STAGES = ['たまご', 'あかちゃん', 'こども', 'おとな'];

export const FORMS = {
  egg: { name: 'ねむたまご', stage: 0, desc: 'しずかな時間で あたたまる、ふしぎなたまご。', hint: 'はじまりの たまご' },
  baby: { name: 'ぷにゅ', stage: 1, desc: 'うまれたての ねむりん。スマホを置くと すやすや育つ。', hint: '20分 スマホを置くと うまれる' },
  moko: { name: 'もこりん', stage: 2, desc: 'たっぷり休んで育った こども。ふわふわの毛が じまん。', hint: 'あかちゃんの間 おせわミスなし' },
  bosa: { name: 'ぼさりん', stage: 2, desc: 'ちょっと ねぶそくな こども。まだ 挽回できるかも。', hint: 'あかちゃんの間に おせわミス…' },
  tsuki: { name: 'つきねむ', stage: 3, desc: '夜にぐっすり眠って育った おとな。ひたいの月が ひかる。', hint: 'もこりんを 夜に たっぷり ねかせる' },
  hidamari: { name: 'ひだまり', stage: 3, desc: '昼間に スマホを置く時間が 多いと育つ、元気なおとな。', hint: 'もこりんを 昼間に 休ませる' },
  kumo: { name: 'くもねむ', stage: 3, desc: 'のんびり マイペースな おとな。ふわふわ 浮かんでいる。', hint: 'のんびり そだてる' },
  neguse: { name: 'ねぐせ', stage: 3, desc: 'ねぶそく気味の おとな。まくらが 手放せない。', hint: 'おせわミスが ちょっと多い' },
  obake: { name: 'おばけねむ', stage: 3, desc: 'ほったらかしに され続けた すがた…。つぎは やさしくね。', hint: 'ぼさりんを ほったらかしに…' },
  kujira: { name: 'ほしくじら', stage: 3, rare: 1, desc: '8時間 いちども起こされなかった子が まれになる、夜空をおよぐ レアキャラ。', hint: 'こどもの間に ながーい夜を…' },
  unicorn: { name: 'ゆめユニコーン', stage: 3, rare: 2, desc: 'いちども おせわミスなく 長い夜を こえた子だけが なれる、でんせつの すがた。', hint: '？？？' },
};

export function newPet(now, rng = Math.random) {
  return {
    name: 'ねむりん', form: 'egg', shiny: rng() < 1 / 20, born: now, xp: 0,
    energy: HEARTS, at: now, zero: null, zeroMiss: 0, lifeMiss: 0,
    miss: 0, night: 0, day: 0, longest: 0, // stats of the current stage, reset on evolution
  };
}

export function newState(now) {
  return { pet: newPet(now), sleep: null, dex: { egg: 1 }, album: [], log: [], days: {}, best: 0, total: 0 };
}

export const dayKey = t => { const d = new Date(t); return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`; };

// Minutes of [s, e) that fall in 22:00–06:00 local time.
export function nightMinutes(s, e) {
  let n = 0;
  for (let t = s; t < e; t += MIN) { const h = new Date(t).getHours(); if (h >= 22 || h < 6) n++; }
  return n;
}

// Settle heart decay and neglect up to `now`. Returns the pet that ran away, if any.
export function tick(st, now) {
  const p = st.pet, dt = Math.max(0, now - p.at);
  p.at = now;
  if (st.sleep || p.form === 'egg') return null; // no decay while asleep; eggs need no care
  if (p.energy > 0) {
    const e = p.energy - dt / DECAY;
    if (e <= 0) { p.zero = now - dt + p.energy * DECAY; p.zeroMiss = 0; }
    p.energy = Math.max(0, e);
  }
  if (p.zero == null) return null;
  const due = 1 + Math.floor((now - p.zero) / (12 * HOUR)); // one mistake when hearts hit 0, then every 12h
  if (due > p.zeroMiss) { p.miss += due - p.zeroMiss; p.lifeMiss += due - p.zeroMiss; p.zeroMiss = due; }
  if (now - p.zero < 72 * HOUR) return null;
  st.pet = newPet(now); // 3 days at zero hearts: runs away
  return p;
}

export function sleep(st, now) {
  tick(st, now);
  st.sleep = { start: now };
}

export function nextForm(p, rng = Math.random) {
  switch (p.form) {
    case 'egg': return 'baby';
    case 'baby': return p.miss ? 'bosa' : 'moko';
    case 'bosa': return p.miss >= 3 ? 'obake' : p.miss ? 'neguse' : 'kumo';
    case 'moko':
      if (!p.miss && p.longest >= 480) { // 8h without touching the phone
        if (!p.lifeMiss && rng() < 0.2) return 'unicorn';
        if (rng() < 0.4) return 'kujira';
      }
      if (p.miss >= 3) return 'neguse';
      if (p.miss >= 2) return 'kumo';
      if (p.day >= 240) return 'hidamari';
      return p.night >= 300 ? 'tsuki' : 'kumo';
  }
}

// End the sleep session. Returns what happened, for the UI.
export function wake(st, now, rng = Math.random) {
  const p = st.pet, start = st.sleep.start, ms = Math.max(0, now - start);
  st.sleep = null;
  p.at = now; // no heart decay while asleep
  if (ms < GRACE) return { kind: 'cancel' };
  const min = Math.floor(Math.min(ms / MIN, MAX_SESSION));
  if (min < EARLY) {
    if (p.form !== 'egg') { p.miss++; p.lifeMiss++; }
    return { kind: 'early', min };
  }
  const night = nightMinutes(start, start + min * MIN);
  p.xp += min; p.night += night; p.day += min - night; p.longest = Math.max(p.longest, min);
  p.energy = Math.min(HEARTS, p.energy + min / 30); p.zero = null; p.zeroMiss = 0;
  const k = dayKey(now);
  st.days[k] = (st.days[k] || 0) + min;
  st.best = Math.max(st.best, min);
  st.total += min;
  st.log = [{ s: start, e: now, min }, ...st.log].slice(0, 50);
  const evolved = [];
  while (FORMS[p.form].stage < 3 && p.xp >= NEXT[FORMS[p.form].stage]) {
    const from = p.form;
    p.form = nextForm(p, rng);
    st.dex[p.form] |= p.shiny ? 2 : 1;
    Object.assign(p, { miss: 0, night: 0, day: 0, longest: 0 });
    evolved.push({ from, to: p.form });
  }
  return { kind: 'ok', min, night, evolved };
}

export const canLeave = p => FORMS[p.form].stage === 3 && p.xp >= NEXT[3];

export function leave(st, now) {
  const p = st.pet;
  st.album = [{ name: p.name, form: p.form, shiny: p.shiny, xp: p.xp, born: p.born, left: now }, ...st.album];
  st.pet = newPet(now);
}

export function streak(st, now) {
  const d = new Date(now);
  if (!st.days[dayKey(d)]) d.setDate(d.getDate() - 1);
  let n = 0;
  while (st.days[dayKey(d)]) { n++; d.setDate(d.getDate() - 1); }
  return n;
}
