import { useEffect, useRef, useState } from 'react'
import { Check, Leaf, Mountain, Waves, TreePine, Settings, Play, Pause, RotateCcw, SkipForward, X, Volume2, LogOut, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'
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
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback } catch { return fallback } }

const FETCH_OPTS = { credentials: 'include' }
const PULSE_KEY = 'rf-session-pulse'
const PAUSE_BACKUP_KEY = 'rf-pause-backup'

async function api(url, options = {}) {
  const res = await fetch(url, {
    ...FETCH_OPTS,
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  })
  let data = null
  try { data = await res.json() } catch {}
  if (!res.ok) {
    const err = new Error(data?.error || `HTTP ${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return { status: res.status, data }
}

function formatTimeHMM(secondsTotal) {
  const v = Math.max(0, Math.floor(secondsTotal))
  const m = Math.floor(v / 60)
  const s = v % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function sessionStartMillis(session) {
  return new Date(`${session.date}T${session.start_time}Z`).getTime()
}

function computeTrueRemaining(startMillis, plannedSec, totalPausedMs, nowMs = Date.now()) {
  const wallMs = Math.max(0, nowMs - startMillis)
  const focusedMs = Math.max(0, wallMs - totalPausedMs)
  return Math.max(0, plannedSec * 1000 - focusedMs)
}

function formatLocalTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatLocalDateTime(date) {
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function App() {
  const [scene, setScene] = useState(() => read('rf-scene', 'forest'))
  const [mode, setMode] = useState('focus')
  const [durations, setDurations] = useState(() => read('rf-durations', { focus: 25, short: 5, long: 15 }))
  const [seconds, setSeconds] = useState(() => durations.focus * 60)
  const [running, setRunning] = useState(false)
  const [task, setTask] = useState(() => read('rf-task', ''))
  const [sound, setSound] = useState(() => read('rf-sound', true))
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [leaves, setLeaves] = useState([])
  const audio = useRef(null)

  const [authed, setAuthed] = useState(null)
  const [authView, setAuthView] = useState('login')
  const [authError, setAuthError] = useState('')
  const [toast, setToast] = useState('')
  const [forbiddenMsg, setForbiddenMsg] = useState('')

  const [currentSession, setCurrentSession] = useState(null)
  const [plannedFocusSeconds, setPlannedFocusSeconds] = useState(durations.focus * 60)

  const totalPausedMsRef = useRef(0)
  const localPauseStartRef = useRef(null)
  const startMillisRef = useRef(0)

  const [sessions, setSessions] = useState([])
  const [expandedRow, setExpandedRow] = useState(null)
  const [rowInterruptions, setRowInterruptions] = useState({})

  const [dailyAnalytics, setDailyAnalytics] = useState([])
  const [heatmapData, setHeatmapData] = useState(Array(24).fill(0))

  const [restoredBanner, setRestoredBanner] = useState('')

  const activeScene = SCENES[scene]; const Icon = activeScene.icon
  const total = durations[mode] * 60; const progress = 1 - Math.min(1, Math.max(0, seconds / Math.max(1, total))); const circumference = 2 * Math.PI * 142
  const time = formatTimeHMM(seconds)

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3500)
  }

  useEffect(() => { localStorage.setItem('rf-scene', JSON.stringify(scene)) }, [scene])
  useEffect(() => { localStorage.setItem('rf-durations', JSON.stringify(durations)) }, [durations])
  useEffect(() => { localStorage.setItem('rf-task', JSON.stringify(task)) }, [task])
  useEffect(() => { localStorage.setItem('rf-sound', JSON.stringify(sound)) }, [sound])

  useEffect(() => {
    if (!running || mode !== 'focus' || !currentSession) return
    const id = setInterval(() => {
      const remainingMs = computeTrueRemaining(
        startMillisRef.current,
        plannedFocusSeconds,
        totalPausedMsRef.current + (localPauseStartRef.current ? (Date.now() - localPauseStartRef.current) : 0)
      )
      setSeconds(Math.ceil(remainingMs / 1000))
    }, 250)
    return () => clearInterval(id)
  }, [running, mode, currentSession, plannedFocusSeconds])

  useEffect(() => {
    if (running && mode !== 'focus') {
      const id = setInterval(() => setSeconds(value => value <= 1 ? 0 : value - 1), 1000)
      return () => clearInterval(id)
    }
  }, [running, mode])

  useEffect(() => {
    if (running && seconds === 0) completeSession()
  }, [seconds, running])

  useEffect(() => {
    if (!authed) return
    const id = setInterval(loadData, 30000)
    return () => clearInterval(id)
  }, [authed])

  useEffect(() => {
    function onVisible() {
      if (document.hidden) return
      if (mode === 'focus' && currentSession) {
        const remainingMs = computeTrueRemaining(
          startMillisRef.current,
          plannedFocusSeconds,
          totalPausedMsRef.current + (localPauseStartRef.current ? (Date.now() - localPauseStartRef.current) : 0)
        )
        setSeconds(Math.ceil(remainingMs / 1000))
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [mode, currentSession, plannedFocusSeconds])

  useEffect(() => {
    function onStorage(e) {
      if (e.key !== PULSE_KEY || !e.newValue) return
      let pulse
      try { pulse = JSON.parse(e.newValue) } catch { return }
      if (!pulse || pulse.sessionId == null || !currentSession || pulse.sessionId !== currentSession.sessionID) return
      if (pulse.auth !== 'same') return
      startMillisRef.current = Number(pulse.startMillis) || startMillisRef.current
      totalPausedMsRef.current = Number(pulse.totalPausedMs) || 0
      if (pulse.localPauseStartIso && pulse.localPauseStartIso !== 'null') {
        localPauseStartRef.current = new Date(pulse.localPauseStartIso).getTime()
        setRunning(false)
      } else {
        localPauseStartRef.current = null
      }
      if (mode === 'focus' && currentSession) {
        const remainingMs = computeTrueRemaining(
          startMillisRef.current,
          plannedFocusSeconds,
          totalPausedMsRef.current + (localPauseStartRef.current ? (Date.now() - localPauseStartRef.current) : 0)
        )
        setSeconds(Math.ceil(remainingMs / 1000))
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [mode, currentSession, plannedFocusSeconds])

  useEffect(() => {
    if (!authed || !currentSession) return
    function writePulse() {
      const payload = JSON.stringify({
        sessionId: currentSession.sessionID,
        auth: 'same',
        startMillis: startMillisRef.current,
        totalPausedMs: totalPausedMsRef.current,
        localPauseStartIso: localPauseStartRef.current ? new Date(localPauseStartRef.current).toISOString() : 'null',
        at: Date.now()
      })
      try { localStorage.setItem(PULSE_KEY, payload) } catch {}
    }
    writePulse()
    const id = setInterval(writePulse, 4000)
    return () => clearInterval(id)
  }, [authed, currentSession])

  useEffect(() => { bootstrap() }, [])

  async function bootstrap() {
    try {
      const { data } = await api('/sessions?status=running')
      setAuthed(true)
      setForbiddenMsg('')
      if (Array.isArray(data) && data.length > 0) {
        const sess = data[0]
        startMillisRef.current = sessionStartMillis(sess)
        const totalPausedServer = Number(sess.paused_ms) || 0
        const serverPausedMarker = sess.last_pause_start_iso ? new Date(sess.last_pause_start_iso).getTime() : null
        let fallbackPausedMs = 0, fallbackMarker = null
        try {
          const backup = JSON.parse(localStorage.getItem(PAUSE_BACKUP_KEY) || 'null')
          if (backup && Number(backup.sessionId) === Number(sess.sessionID)) {
            fallbackPausedMs = Number(backup.totalPausedMs) || 0
            fallbackMarker = backup.localPauseStartIso && backup.localPauseStartIso !== 'null'
              ? new Date(backup.localPauseStartIso).getTime() : null
            if (fallbackPausedMs > totalPausedServer) {
              fallbackPausedMs = fallbackPausedMs
            } else {
              fallbackPausedMs = 0; fallbackMarker = null
            }
          }
        } catch { fallbackPausedMs = 0; fallbackMarker = null }
        totalPausedMsRef.current = totalPausedServer + fallbackPausedMs
        if (serverPausedMarker) {
          localPauseStartRef.current = serverPausedMarker
        } else if (fallbackMarker) {
          localPauseStartRef.current = fallbackMarker
        } else {
          localPauseStartRef.current = null
        }
        let fd = sess.focus_duration
        if (fd == null) {
          fd = durations.focus * 60
          setRestoredBanner(
            'This session was restored from the server. Focus duration reloaded from current settings; pause state has been reconciled from server-stored paused_ms.'
          )
        } else if (totalPausedMsRef.current > 0 || serverPausedMarker) {
          setRestoredBanner(
            'This session was restored from the server. Pause state preserved from server-stored paused_ms and last_pause_start_iso.'
          )
        } else {
          setRestoredBanner('This session was restored from the server.')
        }
        const remainingMs = computeTrueRemaining(startMillisRef.current, fd, totalPausedMsRef.current + (localPauseStartRef.current ? (Date.now() - localPauseStartRef.current) : 0))
        const remainingSec = Math.ceil(remainingMs / 1000)
        setCurrentSession(sess)
        setPlannedFocusSeconds(fd)
        setSeconds(remainingSec)
        setMode('focus')
        setRunning(sess.status === 'running' && !localPauseStartRef.current)
      } else {
        localPauseStartRef.current = null
        totalPausedMsRef.current = 0
        startMillisRef.current = 0
        localStorage.removeItem(PAUSE_BACKUP_KEY)
        localStorage.removeItem(PULSE_KEY)
        setSeconds(durations.focus * 60)
      }
      await loadData()
    } catch (err) {
      if (err.status === 401) {
        setAuthed(false)
      } else if (err.status === 403) {
        setForbiddenMsg(err.data?.error || 'Access denied')
        setAuthed(false)
      } else {
        setAuthed(false)
      }
    }
  }

  async function loadData() {
    try {
      const [sessRes, dailyRes, heatRes] = await Promise.all([
        api('/sessions'),
        api('/analytics/daily'),
        api('/analytics/heatmap'),
      ])
      setSessions(Array.isArray(sessRes.data) ? sessRes.data : [])
      setDailyAnalytics(Array.isArray(dailyRes.data) ? dailyRes.data : [])
      const padded = Array(24).fill(0)
      if (Array.isArray(heatRes.data)) {
        for (const row of heatRes.data) {
          if (typeof row.hour === 'number' && row.hour >= 0 && row.hour < 24) {
            padded[row.hour] = Number(row.count) || 0
          }
        }
      }
      setHeatmapData(padded)
    } catch (err) {
      if (err.status === 401) setAuthed(false)
    }
  }

  async function handleLogin(username, password) {
    setAuthError('')
    try {
      await api('/auth/login', { method: 'POST', body: { username, password } })
      setAuthView('login')
      await bootstrap()
    } catch (err) {
      if (err.status === 400 || err.status === 401) {
        setAuthError(err.data?.error || 'Login failed')
      } else {
        setAuthError('Network error. Is Flask running on 127.0.0.1:5000?')
      }
    }
  }

  async function handleSignup(username, email, password) {
    setAuthError('')
    try {
      await api('/auth/signup', { method: 'POST', body: { username, email, password } })
      await bootstrap()
    } catch (err) {
      if (err.status === 400 || err.status === 409) {
        setAuthError(err.data?.error || 'Signup failed')
      } else {
        setAuthError('Network error. Is Flask running on 127.0.0.1:5000?')
      }
    }
  }

  async function handleLogout() {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch {}
    localStorage.clear()
    setAuthed(false)
    setAuthView('login')
    setAuthError('')
    setCurrentSession(null)
    setRunning(false)
    setSeconds(durations.focus * 60)
    setSessions([])
    setDailyAnalytics([])
    setHeatmapData(Array(24).fill(0))
    setRowInterruptions({})
    setExpandedRow(null)
    setTask('')
    setForbiddenMsg('')
    setRestoredBanner('')
    totalPausedMsRef.current = 0
    localPauseStartRef.current = null
    startMillisRef.current = 0
  }

  function burst(kind = 'leaf') {
    const batch = Array.from({ length: 9 }, (_, i) => ({
      id: `${Date.now()}-${i}`, left: 40 + Math.random() * 20,
      delay: Math.random() * .18, rotate: Math.random() * 70 - 35, kind
    }))
    setLeaves(batch)
    window.setTimeout(() => setLeaves([]), 1250)
  }

  function writePauseBackup() {
    if (!currentSession) return
    try {
      localStorage.setItem(PAUSE_BACKUP_KEY, JSON.stringify({
        sessionId: currentSession.sessionID,
        totalPausedMs: totalPausedMsRef.current,
        localPauseStartIso: localPauseStartRef.current ? new Date(localPauseStartRef.current).toISOString() : 'null',
        at: Date.now()
      }))
    } catch {}
  }

  async function startSession() {
    if (mode !== 'focus') {
      setRunning(true)
      burst('leaf')
      return
    }
    const focusMin = Math.max(1, Math.min(180, Number(durations.focus) || 25))
    const focusSec = focusMin * 60
    try {
      const { data } = await api('/sessions', {
        method: 'POST',
        body: { start_time: new Date().toISOString(), focus_duration: focusSec }
      })
      startMillisRef.current = sessionStartMillis(data)
      totalPausedMsRef.current = Number(data.paused_ms) || 0
      localPauseStartRef.current = null
      setCurrentSession(data)
      setPlannedFocusSeconds(data.focus_duration || focusSec)
      setSeconds(data.focus_duration || focusSec)
      setRunning(true)
      setRestoredBanner('')
      localStorage.removeItem(PAUSE_BACKUP_KEY)
      burst('leaf')
    } catch (err) {
      if (err.status === 401) { setAuthed(false); return }
      if (err.status === 403) { setForbiddenMsg(err.data?.error || 'Access denied'); return }
      if (err.status === 409) {
        showToast(err.data?.error || 'A running session exists — reconciling…')
        await bootstrap()
        return
      }
      showToast(err.data?.error || `Failed to start session: ${err.message}`)
    }
  }

  async function patchPauseState(newServerStatus) {
    if (!currentSession) return
    const payload = {
      status: newServerStatus,
      paused_ms: totalPausedMsRef.current
    }
    if (localPauseStartRef.current) {
      payload.last_pause_start_iso = new Date(localPauseStartRef.current).toISOString()
    } else {
      payload.last_pause_start_iso = null
    }
    try {
      await api(`/sessions/${currentSession.sessionID}`, { method: 'PATCH', body: payload })
      writePauseBackup()
    } catch (err) {
      writePauseBackup()
      if (err.status === 401) { setAuthed(false); return }
      if (err.status === 403) { setForbiddenMsg(err.data?.error || 'Access denied'); return }
      if (err.status !== 409) {
        showToast((err.data?.error || 'Server unreachable — pause state saved locally.') + ' Local-only backup will merge on next reload.')
      }
    }
  }

  async function toggleRun() {
    if (mode !== 'focus') {
      if (running) { setRunning(false); burst('stone') }
      else { setRunning(true); burst('leaf') }
      return
    }
    if (!running && !currentSession) {
      startSession()
      return
    }
    if (!running) {
      if (localPauseStartRef.current) {
        const closedPauseMs = Date.now() - localPauseStartRef.current
        totalPausedMsRef.current += closedPauseMs
        localPauseStartRef.current = null
        await patchPauseState('running')
      } else if (currentSession && currentSession.status === 'paused') {
        await patchPauseState('running')
      }
      const remainingMs = computeTrueRemaining(
        startMillisRef.current,
        plannedFocusSeconds,
        totalPausedMsRef.current
      )
      setSeconds(Math.ceil(remainingMs / 1000))
      setRunning(true)
      burst('leaf')
      return
    }
    setRunning(false)
    localPauseStartRef.current = Date.now()
    await patchPauseState('paused')
    burst('stone')
  }

  async function completeSession() {
    if (mode === 'focus' && currentSession) {
      const nowMs = Date.now()
      if (localPauseStartRef.current) {
        totalPausedMsRef.current += (nowMs - localPauseStartRef.current)
        localPauseStartRef.current = null
      }
      const focusedMs = Math.max(1, (nowMs - startMillisRef.current) - totalPausedMsRef.current)
      const actualElapsed = Math.max(1, Math.ceil(focusedMs / 1000))
      try {
        const endHMS = new Date().toISOString().slice(11, 19)
        await api(`/sessions/${currentSession.sessionID}`, {
          method: 'PATCH',
          body: { status: 'completed', end_time: endHMS, duration: actualElapsed, paused_ms: totalPausedMsRef.current, last_pause_start_iso: null }
        })
        burst('leaf')
        if (sound) audio.current?.play().catch(() => {})
      } catch (err) {
        if (err.status === 401) { setAuthed(false); return }
        if (err.status === 403) { setForbiddenMsg(err.data?.error || 'Access denied'); return }
        showToast(err.data?.error || `Failed to complete: ${err.message}`)
      }
    } else if (mode === 'focus' && sound) {
      audio.current?.play().catch(() => {})
      burst('leaf')
    }
    setCurrentSession(null)
    setRunning(false)
    setRestoredBanner('')
    setSeconds(durations[mode] * 60)
    totalPausedMsRef.current = 0
    localPauseStartRef.current = null
    startMillisRef.current = 0
    localStorage.removeItem(PAUSE_BACKUP_KEY)
    setTimeout(loadData, 200)
  }

  async function logInterruption() {
    if (!currentSession) return
    try {
      await api(`/sessions/${currentSession.sessionID}/interruptions`, {
        method: 'POST',
        body: { timestamp: new Date().toISOString() }
      })
      burst('stone')
    } catch (err) {
      if (err.status === 401) { setAuthed(false); return }
      if (err.status === 403) { setForbiddenMsg(err.data?.error || 'Access denied'); return }
      showToast(err.data?.error || `Failed to log interruption: ${err.message}`)
    }
  }

  function changeMode(next) {
    if (mode === 'focus' && currentSession) {
      showToast('Complete or stop the current focus session first.')
      return
    }
    setMode(next); setRunning(false); setSeconds(durations[next] * 60); burst('leaf')
  }
  function changeScene(next) { if (next === scene) return; setScene(next); burst('leaf') }
  function reset() {
    if (mode === 'focus' && currentSession) {
      showToast('Resetting client-side display only. Server focus start and total_paused_ms are unchanged; use Stop & Discard for that.')
    }
    setRunning(false)
    if (mode === 'focus' && currentSession) {
      const remainingMs = computeTrueRemaining(
        startMillisRef.current,
        plannedFocusSeconds,
        totalPausedMsRef.current + (localPauseStartRef.current ? (Date.now() - localPauseStartRef.current) : 0)
      )
      setSeconds(Math.ceil(remainingMs / 1000))
    } else {
      setSeconds(durations[mode] * 60)
    }
    burst('stone')
  }
  function skip() { changeMode(mode === 'focus' ? 'short' : 'focus') }

  function updateDuration(key, value) {
    const cap = key === 'focus' ? 180 : 120
    const next = Math.max(1, Math.min(cap, Number(value) || 1))
    setDurations(d => ({ ...d, [key]: next }))
    if (key === mode && !running && mode !== 'focus') setSeconds(next * 60)
    if (key === 'focus' && !running && mode === 'focus' && !currentSession) {
      setPlannedFocusSeconds(next * 60)
      setSeconds(next * 60)
    }
  }

  async function toggleExpand(sessionID) {
    const isExpanded = expandedRow === sessionID
    if (isExpanded) { setExpandedRow(null); return }
    setExpandedRow(sessionID)
    if (rowInterruptions[sessionID] != null) return
    try {
      const { data } = await api(`/sessions/${sessionID}/interruptions`)
      setRowInterruptions(prev => ({ ...prev, [sessionID]: Array.isArray(data) ? data : [] }))
    } catch (err) {
      if (err.status === 401) { setAuthed(false); return }
      if (err.status === 403) { setForbiddenMsg(err.data?.error || 'Access denied'); return }
      setRowInterruptions(prev => ({ ...prev, [sessionID]: [] }))
      showToast(err.data?.error || 'Could not load interruptions')
    }
  }

  const todayFocusMinutes = dailyAnalytics.length > 0
    ? (dailyAnalytics[dailyAnalytics.length - 1].focus_minutes || 0)
    : 0
  const activeDays = dailyAnalytics.filter(d => (d.focus_minutes || 0) > 0).length
  const maxBar = dailyAnalytics.reduce((m, d) => Math.max(m, d.focus_minutes || 0), 0)
  const maxHeat = heatmapData.reduce((m, c) => Math.max(m, c), 0)

  if (authed === null) {
    return <div className="boot-screen"><p>Loading…</p></div>
  }

  if (!authed) {
    return (
      <AuthScreen
        view={authView}
        onToggle={() => { setAuthView(v => v === 'login' ? 'signup' : 'login'); setAuthError('') }}
        onLogin={handleLogin}
        onSignup={handleSignup}
        error={authError}
        forbidden={forbiddenMsg}
      />
    )
  }

  const startButtonLabel = running
    ? 'Pause'
    : (currentSession && seconds < plannedFocusSeconds)
      ? 'Resume'
      : `Start ${MODES[mode].label.toLowerCase()}`
  const StartStopIcon = running ? Pause : Play

  return (
    <main className={`app tone-${activeScene.tone} ${running ? 'running' : ''}`}>
      <div className="scene-image" style={{ backgroundImage: `url(${activeScene.image})` }} />
      <div className="scene-wash" />
      <div className="scene-mist mist-one" />
      <div className="scene-mist mist-two" />
      <div className="leaf-layer" aria-hidden="true">
        {leaves.map(leaf => (
          <span key={leaf.id} className={`falling-leaf ${leaf.kind}`} style={{ left: `${leaf.left}%`, animationDelay: `${leaf.delay}s`, transform: `rotate(${leaf.rotate}deg)` }}>
            <Leaf size={18} fill="currentColor" />
          </span>
        ))}
      </div>
      <audio ref={audio} src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQAAAAA=" />
      {toast && <div className="toast">{toast}</div>}
      {forbiddenMsg && (
        <div className="toast toast-err"><AlertCircle size={14} /> {forbiddenMsg}</div>
      )}
      {restoredBanner && (
        <div className="restore-banner"><AlertCircle size={14} /> {restoredBanner}</div>
      )}

      <header className="header">
        <div className="brand">
          <span className="brand-symbol"><Leaf size={17}/></span>
          <div><strong>Resilient</strong><small>Focus</small></div>
        </div>
        <nav>
          <button className="active">Focus</button>
          <button onClick={() => document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' })}>Sessions</button>
          <button onClick={() => setSettingsOpen(true)}>Settings</button>
        </nav>
        <div className="header-actions">
          <button className="logout-button" onClick={handleLogout} aria-label="Log out"><LogOut size={16} /> Log out</button>
          <button className="mobile-settings" onClick={() => setSettingsOpen(true)} aria-label="Open settings"><Settings size={18}/></button>
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow"><span /> {running ? 'In your flow' : 'A quiet place to begin'}</p>
        <h1>Make room for <em>focus.</em></h1>
        <p className="subtitle">Settle into the moment. Let the world wait.</p>
        <div className="timer-wrap">
          <div className="timer-glow"/>
          <svg viewBox="0 0 320 320" className="progress-ring">
            <circle cx="160" cy="160" r="142" className="ring-track"/>
            <circle cx="160" cy="160" r="142" className="ring-value" strokeDasharray={`${circumference * progress} ${circumference}`} />
          </svg>
          <div className="timer-core">
            <span>{MODES[mode].label.toUpperCase()}</span>
            <strong>{time}</strong>
            <small>{running ? 'Stay with it' : localPauseStartRef.current ? 'Paused — resume when ready' : 'Ready when you are'}</small>
          </div>
        </div>
        <div className="mode-tabs">
          {Object.entries(MODES).map(([key, value]) => (
            <button key={key} className={mode === key ? 'selected' : ''} onClick={() => changeMode(key)}>{value.label}</button>
          ))}
        </div>
        <div className="controls">
          <button className="icon-button" onClick={reset} aria-label="Reset timer display"><RotateCcw size={17}/></button>
          <button className="start-button" onClick={toggleRun}>
            <StartStopIcon size={18} fill="currentColor"/>
            <span>{startButtonLabel}</span>
          </button>
          <button className="icon-button" onClick={skip} aria-label="Skip session"><SkipForward size={17}/></button>
        </div>
        <div className="controls intrusion-row">
          <button
            className="intrusion-button"
            disabled={!running || mode !== 'focus' || !currentSession}
            onClick={logInterruption}
          >
            Log interruption
          </button>
        </div>
        <div className="focus-input">
          <label>CURRENTLY FOCUSING ON</label>
          <input
            value={task}
            onChange={event => setTask(event.target.value)}
            placeholder="What are you focusing on? (not saved to server)"
          />
          <small className="input-hint">This note is kept in-browser only and is not persisted to the backend.</small>
        </div>
      </section>

      <section className="workspace">
        <div className="glass-panel scene-panel">
          <div className="panel-heading">
            <div><label>ATMOSPHERE</label><h2>Choose your surroundings</h2></div>
            <span className="scene-name"><Icon size={14}/> {activeScene.label}</span>
          </div>
          <div className="scene-grid">
            {Object.entries(SCENES).map(([key, value]) => {
              const SceneIcon = value.icon
              return (
                <button className={`scene-choice ${scene === key ? 'selected' : ''}`} key={key} onClick={() => changeScene(key)}>
                  <SceneIcon size={20}/><span>{value.label}</span>
                  {scene === key && <Check size={15}/>}
                </button>
              )
            })}
          </div>
        </div>

        <div className="glass-panel stats-panel">
          <div className="panel-heading">
            <div><label>YOUR RHYTHM</label><h2>Today, gently</h2></div>
          </div>
          <div className="stats">
            <div>
              <strong>{Math.floor(todayFocusMinutes / 60)}<small>h</small> {todayFocusMinutes % 60}<small>m</small></strong>
              <span>Today's focus</span>
            </div>
            <div>
              <strong>{sessions.length}</strong>
              <span>Sessions</span>
            </div>
            <div>
              <strong>{activeDays}<small>/7</small></strong>
              <span>Active days</span>
            </div>
          </div>
          <div className="week">
            <label>THIS WEEK</label>
            <div className="bars">
              {dailyAnalytics.map((day, index) => {
                const h = maxBar > 0 ? Math.round(((day.focus_minutes || 0) / maxBar) * 100) : 0
                const label = new Date(`${day.date}T00:00:00Z`).toLocaleDateString([], { weekday: 'short' }).charAt(0)
                const isToday = index === dailyAnalytics.length - 1
                return (
                  <div className={isToday ? 'today' : ''} key={day.date}>
                    <i style={{ height: `${Math.max(4, h)}%` }}/>
                    <small title={day.date}>{label}</small>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="heatmap">
            <label>SESSIONS STARTED (this range)</label>
            <div className="heatmap-grid">
              {heatmapData.map((count, h) => {
                const intensity = maxHeat > 0 ? Math.min(1, count / Math.max(1, maxHeat)) : 0
                const bg = intensity === 0
                  ? 'rgba(165,209,161,.12)'
                  : `rgba(177, 223, 168, ${0.18 + intensity * 0.78})`
                return (
                  <div
                    key={h}
                    className="heat-cell"
                    title={`Hour ${String(h).padStart(2, '0')}: ${count} session${count === 1 ? '' : 's'}`}
                    style={{ background: bg, boxShadow: count > 0 && intensity > 0.6 ? '0 0 10px rgba(177,223,168,.35)' : 'none' }}
                  >
                    <span className="heat-hour">{String(h).padStart(2, '0')}</span>
                    <span className="heat-count">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="history" id="history">
        <div className="history-heading">
          <div><label>THE TRAIL SO FAR</label><h2>Sessions</h2></div>
          <span>{sessions.length} completed</span>
        </div>
        {sessions.length === 0 && (
          <div className="history-empty">No completed sessions yet. Start a focus session above.</div>
        )}
        {sessions.map((s) => {
          const startUTC = new Date(`${s.date}T${s.start_time}Z`)
          const mins = Math.max(0, Math.floor((s.duration || 0) / 60))
          const isExpanded = expandedRow === s.sessionID
          const ints = rowInterruptions[s.sessionID]
          return (
            <div className={`history-row-group ${isExpanded ? 'open' : ''}`} key={s.sessionID}>
              <button className="history-row" onClick={() => toggleExpand(s.sessionID)}>
                <time>{formatLocalTime(startUTC)}</time>
                <b><Check size={12}/></b>
                <div className="row-main">
                  <p>Focused session</p>
                  {s.interruption_count > 0 && <small className="int-count">{s.interruption_count} interruption{s.interruption_count === 1 ? '' : 's'}</small>}
                </div>
                <small>{mins} min</small>
                <span className="row-chevron">{isExpanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}</span>
              </button>
              {isExpanded && (
                <div className="row-expand">
                  <div className="row-expand-meta">
                    <span className="meta-item">Started: {formatLocalDateTime(startUTC)}</span>
                    <span className="meta-item">Status: {s.status}</span>
                  </div>
                  <label>Interruption log</label>
                  {ints == null && <div className="ints-loading">Loading interruptions…</div>}
                  {ints != null && ints.length === 0 && <div className="ints-empty">no interruptions</div>}
                  {ints != null && ints.length > 0 && (
                    <ul className="ints-list">
                      {ints.map((row) => {
                        const d = new Date(row.timestamp)
                        return (
                          <li key={row.interruptionID}>
                            <time>{formatLocalDateTime(d)}</time>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </section>

      <footer><span>© 2025 Resilient Focus</span><span><Leaf size={13}/> Built for steady progress</span></footer>

      {settingsOpen && (
        <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && setSettingsOpen(false)}>
          <div className="modal">
            <div className="modal-top">
              <div><label>PERSONALIZE</label><h2>Settings</h2></div>
              <button onClick={() => setSettingsOpen(false)} aria-label="Close settings"><X/></button>
            </div>
            <div className="duration-settings">
              <label>Timer durations <small>minutes</small></label>
              {Object.entries(MODES).map(([key, value]) => (
                <div className="setting-row" key={key}>
                  <span>{value.label}</span>
                  <input
                    type="number"
                    min="1"
                    max={key === 'focus' ? 180 : 120}
                    value={durations[key]}
                    onChange={event => updateDuration(key, event.target.value)}
                  />
                </div>
              ))}
            </div>
            <div className="setting-row sound">
              <span><Volume2 size={16}/> Sound cues</span>
              <button className={`toggle ${sound ? 'on' : ''}`} onClick={() => setSound(value => !value)} aria-label="Toggle sound"><i/></button>
            </div>
            <button className="save-button" onClick={() => setSettingsOpen(false)}>Save changes</button>
          </div>
        </div>
      )}
    </main>
  )
}

function AuthScreen({ view, onToggle, onLogin, onSignup, error, forbidden }) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSubmitting(true)
    try {
      if (view === 'login') {
        await onLogin(username.trim(), password)
      } else {
        await onSignup(username.trim(), email.trim(), password)
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="app tone-green auth-app">
      <div className="scene-image" style={{ backgroundImage: `url(${forest})` }} />
      <div className="scene-wash" />
      <div className="scene-mist mist-one" />
      <div className="scene-mist mist-two" />
      <div className="auth-wrap">
        <div className="auth-brand">
          <span className="brand-symbol"><Leaf size={19}/></span>
          <div><strong>Resilient</strong><small>Focus</small></div>
        </div>
        <form className="glass-panel auth-panel" onSubmit={submit}>
          <div className="panel-heading center">
            <div>
              <label>WELCOME</label>
              <h2>{view === 'login' ? 'Sign in to continue' : 'Create your account'}</h2>
            </div>
          </div>
          {error && <div className="auth-err"><AlertCircle size={14} /> {error}</div>}
          {forbidden && <div className="auth-err auth-err-warn"><AlertCircle size={14} /> {forbidden}</div>}
          <div className="field">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="focus-input-auth"
              placeholder="e.g. arya"
            />
          </div>
          {view === 'signup' && (
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="focus-input-auth"
                placeholder="you@example.com"
              />
            </div>
          )}
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete={view === 'login' ? 'current-password' : 'new-password'}
              className="focus-input-auth"
              placeholder="••••••••"
            />
          </div>
          <button className="save-button auth-submit" type="submit" disabled={submitting}>
            {submitting ? 'Please wait…' : (view === 'login' ? 'Sign in' : 'Create account')}
          </button>
          <div className="auth-toggle">
            {view === 'login' ? (
              <>New here? <button type="button" onClick={onToggle}>Create account</button></>
            ) : (
              <>Already have an account? <button type="button" onClick={onToggle}>Sign in</button></>
            )}
          </div>
          <small className="auth-hint">
            Flask must be running on <code>127.0.0.1:5000</code> and Vite on <code>127.0.0.1:5173</code>.
          </small>
        </form>
      </div>
    </main>
  )
}
