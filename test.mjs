// node test.mjs — checks the game rules in game.js
import assert from 'node:assert/strict';
import { newState, newPet, sleep, wake, tick, nightMinutes, streak, canLeave, leave, MIN, HOUR } from './game.js';

let t, st;
const nap = (min, rng = () => 0.99) => { sleep(st, t); t += min * MIN; return wake(st, t, rng); };
const reset = (h = 23) => { t = new Date(2026, 8, 30, h, 0).getTime(); st = newState(t); };

// cancel within grace, early wake of an egg is no mistake, 20 min hatches
reset();
sleep(st, t); assert.equal(wake(st, t + 5e3).kind, 'cancel');
assert.equal(nap(3).kind, 'early');
assert.equal(st.pet.lifeMiss, 0);
assert.deepEqual(nap(30).evolved.map(e => e.to), ['baby']);
assert.ok(st.dex.baby);

// a mistake as a baby -> bosa; neglect as bosa -> obake
assert.equal(nap(2).kind, 'early');
assert.equal(st.pet.miss, 1);
assert.deepEqual(nap(200).evolved.map(e => e.to), ['bosa']);
assert.equal(st.pet.miss, 0);
t += 20 * HOUR; tick(st, t);             // 4 hearts gone after 20h awake
assert.equal(st.pet.energy, 0);
assert.equal(st.pet.miss, 1);
t += 24 * HOUR; tick(st, t);             // +2 more mistakes over the next 24h at zero
assert.equal(st.pet.miss, 3);
assert.equal(nap(700).evolved[0].to, 'obake');
assert.ok(canLeave(st.pet) === false);

// runaway after 3 days at zero hearts
t += 20 * HOUR + 72 * HOUR;
const ran = tick(st, t);
assert.equal(ran.form, 'obake');
assert.equal(st.pet.form, 'egg');

// perfect care + 8h night as a child -> legendary unicorn (rng forced)
reset();
assert.deepEqual(nap(480).evolved.map(e => e.to), ['baby', 'moko']);
assert.equal(nap(480, () => 0).evolved[0].to, 'unicorn');
assert.equal(st.pet.energy, 4);

// day-time rests as a child -> hidamari; night rests -> tsuki
reset(10);
nap(200);                                // egg -> baby -> moko
assert.equal(nap(300).evolved.length, 0); // 10:00+ day minutes
assert.equal(nap(420).evolved[0].to, 'hidamari');
reset(22);
nap(200);                                // hatch + grow during 22:00-01:20
t = new Date(2026, 9, 1, 22, 0).getTime();
assert.equal(nap(710).evolved[0].to, 'tsuki');     // 480 night min, 230 day min

// leaving home, streak, night split
while (!canLeave(st.pet)) nap(700);
leave(st, t);
assert.equal(st.album.length, 1);
assert.equal(st.pet.form, 'egg');
assert.ok(streak(st, t) >= 2);
const d = new Date(2026, 8, 30, 21, 0).getTime();
assert.equal(nightMinutes(d, d + 120 * MIN), 60);
assert.equal(newPet(0, () => 0).shiny, true);

console.log('ok');
