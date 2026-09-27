import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Leaf, Mountain, Waves, TreePine, Settings, Play, Pause, RotateCcw, SkipForward, X, Volume2 } from 'lucide-react'
import forest from './assets/forest-reference.png'
import mountain from './assets/mountain-scene.jpg'
import ocean from './assets/ocean-scene.jpg'
import beach from './assets/beach-scene.jpg'

const MODES = { focus: { label: 'Focus', minutes: 25 }, short: { label: 'Short break', minutes: 5 }, long: { label: 'Long break', minutes: 15 } }
const SCENES = {
  mountain: { label: 'Mountain', image: mountain, icon: Mountain, tone: 'cool' },
  forest: { label: 'Forest', image: forest, icon: TreePine, tone: 'green' },
  ocean: { label: 'Ocean', image: ocean, icon: Waves, tone: 'blue' },
  beach: { label: 'Beach', image: beach, icon: Leaf, tone: 'sand' },
}
const starterHistory = [{ time: '09:00', task: 'Deep work', duration: 25 }, { time: '10:15', task: 'Study notes', duration: 25 }, { time: '12:30', task: 'Project planning', duration: 50 }]
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback } catch { return fallback } }

export default function App() {
  const [scene, setScene] = useState(() => read('rf-scene', 'forest'))
  const [mode, setMode] = useState('focus')
  const [durations, setDurations] = useState(() => read('rf-durations', { focus: 25, short: 5, long: 15 }))
  const [seconds, setSeconds] = useState(() => durations.focus * 60)
  const [running, setRunning] = useState(false)
  const [task, setTask] = useState(() => read('rf-task', 'Build my project'))
  const [sessions, setSessions] = useState(() => read('rf-sessions', 6))
  const [history, setHistory] = useState(() => read('rf-history', starterHistory))
  const [sound, setSound] = useState(() => read('rf-sound', true))
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [leaves, setLeaves] = useState([])
  const audio = useRef(null)
  const current = MODES[mode]; const activeScene = SCENES[scene]; const Icon = activeScene.icon
  const total = durations[mode] * 60; const progress = 1 - seconds / total; const circumference = 2 * Math.PI * 142
  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  useEffect(() => localStorage.setItem('rf-scene', JSON.stringify(scene)), [scene])
  useEffect(() => localStorage.setItem('rf-durations', JSON.stringify(durations)), [durations])
  useEffect(() => localStorage.setItem('rf-task', JSON.stringify(task)), [task])
  useEffect(() => localStorage.setItem('rf-sessions', JSON.stringify(sessions)), [sessions])
  useEffect(() => localStorage.setItem('rf-history', JSON.stringify(history)), [history])
  useEffect(() => localStorage.setItem('rf-sound', JSON.stringify(sound)), [sound])
  useEffect(() => { if (!running) return; const id = setInterval(() => setSeconds(value => value <= 1 ? 0 : value - 1), 1000); return () => clearInterval(id) }, [running])
  useEffect(() => { if (running && seconds === 0) completeSession() }, [seconds, running])

  function burst(kind = 'leaf') { const batch = Array.from({ length: 9 }, (_, i) => ({ id: `${Date.now()}-${i}`, left: 40 + Math.random() * 20, delay: Math.random() * .18, rotate: Math.random() * 70 - 35, kind })); setLeaves(batch); window.setTimeout(() => setLeaves([]), 1250) }
  function completeSession() { setRunning(false); if (mode === 'focus') { setSessions(n => n + 1); setHistory(items => [{ time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), task: task || 'Focused session', duration: durations.focus }, ...items]); burst('leaf'); if (sound) audio.current?.play().catch(() => {}) } }
  function changeMode(next) { setMode(next); setRunning(false); setSeconds(durations[next] * 60); burst('leaf') }
  function changeScene(next) { if (next === scene) return; setScene(next); burst('leaf') }
  function reset() { setRunning(false); setSeconds(durations[mode] * 60); burst('stone') }
  function skip() { changeMode(mode === 'focus' ? 'short' : 'focus') }
  function updateDuration(key, value) { const next = Math.max(1, Math.min(120, Number(value) || 1)); setDurations(d => ({ ...d, [key]: next })); if (key === mode && !running) setSeconds(next * 60) }

  return <main className={`app tone-${activeScene.tone} ${running ? 'running' : ''}`}>
    <div className="scene-image" style={{ backgroundImage: `url(${activeScene.image})` }} /><div className="scene-wash" /><div className="scene-mist mist-one" /><div className="scene-mist mist-two" /><div className="leaf-layer" aria-hidden="true">{leaves.map(leaf => <span key={leaf.id} className={`falling-leaf ${leaf.kind}`} style={{ left: `${leaf.left}%`, animationDelay: `${leaf.delay}s`, transform: `rotate(${leaf.rotate}deg)` }}><Leaf size={18} fill="currentColor" /></span>)}</div>
    <audio ref={audio} src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=" />
    <header className="header"><div className="brand"><span className="brand-symbol"><Leaf size={17}/></span><div><strong>Resilient</strong><small>Focus</small></div></div><nav><button className="active">Focus</button><button onClick={() => document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' })}>Sessions</button><button onClick={() => setSettingsOpen(true)}>Settings</button></nav><button className="mobile-settings" onClick={() => setSettingsOpen(true)} aria-label="Open settings"><Settings size={18}/></button></header>
    <section className="hero"><p className="eyebrow"><span /> {running ? 'In your flow' : 'A quiet place to begin'}</p><h1>Make room for <em>focus.</em></h1><p className="subtitle">Settle into the moment. Let the world wait.</p>
      <div className="timer-wrap"><div className="timer-glow"/><svg viewBox="0 0 320 320" className="progress-ring"><circle cx="160" cy="160" r="142" className="ring-track"/><circle cx="160" cy="160" r="142" className="ring-value" strokeDasharray={`${circumference * progress} ${circumference}`} /></svg><div className="timer-core"><span>{current.label.toUpperCase()}</span><strong>{time}</strong><small>{running ? 'Stay with it' : 'Ready when you are'}</small></div></div>
      <div className="mode-tabs">{Object.entries(MODES).map(([key, value]) => <button key={key} className={mode === key ? 'selected' : ''} onClick={() => changeMode(key)}>{value.label}</button>)}</div>
      <div className="controls"><button className="icon-button" onClick={reset} aria-label="Reset timer"><RotateCcw size={17}/></button><button className="start-button" onClick={() => { setRunning(value => !value); burst('leaf') }}>{running ? <Pause size={18} fill="currentColor"/> : <Play size={18} fill="currentColor"/>}<span>{running ? 'Pause' : seconds < total ? 'Resume' : 'Start focus'}</span></button><button className="icon-button" onClick={skip} aria-label="Skip session"><SkipForward size={17}/></button></div>
      <div className="focus-input"><label>CURRENTLY FOCUSING ON</label><input value={task} onChange={event => setTask(event.target.value)} placeholder="What are you focusing on?" /></div>
    </section>
    <section className="workspace"><div className="glass-panel scene-panel"><div className="panel-heading"><div><label>ATMOSPHERE</label><h2>Choose your surroundings</h2></div><span className="scene-name"><Icon size={14}/> {activeScene.label}</span></div><div className="scene-grid">{Object.entries(SCENES).map(([key, value]) => { const SceneIcon = value.icon; return <button className={`scene-choice ${scene === key ? 'selected' : ''}`} key={key} onClick={() => changeScene(key)}><SceneIcon size={20}/><span>{value.label}</span>{scene === key && <Check size={15}/>}</button> })}</div></div><div className="glass-panel stats-panel"><div className="panel-heading"><div><label>YOUR RHYTHM</label><h2>Today, gently</h2></div><span className="streak">✦ {Math.max(4, Math.floor(sessions / 2))} day streak</span></div><div className="stats"><div><strong>{Math.floor(sessions * 25 / 60)}<small>h</small> {sessions * 25 % 60}<small>m</small></strong><span>Today's focus</span></div><div><strong>{sessions}</strong><span>Sessions</span></div><div><strong>84<small>%</small></strong><span>Consistency</span></div></div><div className="week"><label>THIS WEEK</label><div className="bars">{[35,52,28,72,48,86,24].map((height, index) => <div className={index === 4 ? 'today' : ''} key={index}><i style={{ height: `${height}%` }}/><small>{['M','T','W','T','F','S','S'][index]}</small></div>)}</div></div></div></section>
    <section className="history" id="history"><div className="history-heading"><div><label>THE TRAIL SO FAR</label><h2>Today's sessions</h2></div><span>{history.length} completed</span></div>{history.slice(0, 5).map((item, index) => <div className="history-row" key={`${item.time}-${index}`}><time>{item.time}</time><b><Check size={12}/></b><p>{item.task}</p><small>{item.duration} min</small></div>)}</section>
    <footer><span>© 2025 Resilient Focus</span><span><Leaf size={13}/> Built for steady progress</span></footer>
    {settingsOpen && <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && setSettingsOpen(false)}><div className="modal"><div className="modal-top"><div><label>PERSONALIZE</label><h2>Settings</h2></div><button onClick={() => setSettingsOpen(false)} aria-label="Close settings"><X/></button></div><div className="duration-settings"><label>Timer durations <small>minutes</small></label>{Object.entries(MODES).map(([key, value]) => <div className="setting-row" key={key}><span>{value.label}</span><input type="number" min="1" max="120" value={durations[key]} onChange={event => updateDuration(key, event.target.value)}/></div>)}</div><div className="setting-row sound"><span><Volume2 size={16}/> Sound cues</span><button className={`toggle ${sound ? 'on' : ''}`} onClick={() => setSound(value => !value)} aria-label="Toggle sound"><i/></button></div><button className="save-button" onClick={() => setSettingsOpen(false)}>Save changes</button></div></div>}
  </main>
}
