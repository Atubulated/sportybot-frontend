"use client";

import { useState, useEffect } from "react";

import { API_URL } from '../../lib/config';

// Type definitions
interface Prediction {
  id: string;
  slip_id: string;
  match_name: string;
  league: string;
  selected_market: string;
  estimated_odds: number;
  confidence: number;
  status: "PENDING" | "WON" | "LOST" | "ANALYZED";
  match_date?: string;
  actual_result?: string;
  risk_profile: string;
  target_odds: number;
  created_at: string;
  reasoning?: string;
}

interface GroupedSlip {
  slip_id: string;
  picks: Prediction[];
  target_odds: number;
  risk_profile: string;
  date_generated: string;
  status: string;
}

export default function Home() {
  const [targetOdds, setTargetOdds] = useState(10);
  const [riskProfile, setRiskProfile] = useState("safe");
  const [loading, setLoading] = useState(false);
  const [updatingResults, setUpdatingResults] = useState(false);
  const [analyzingDaily, setAnalyzingDaily] = useState(false);
  const [currentSlip, setCurrentSlip] = useState<any>(null);
  const [history, setHistory] = useState<Prediction[]>([]);
  const [analyzedMatches, setAnalyzedMatches] = useState<Prediction[]>([]);
  const [selectedMatches, setSelectedMatches] = useState<string[]>([]);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);
  const [expandedSlips, setExpandedSlips] = useState<Set<string>>(new Set());
  const [showBrowseMatches, setShowBrowseMatches] = useState(false);

  useEffect(() => {
    fetchHistory();
    fetchAnalyzedMatches();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/history`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setHistory(data.reverse());
      }
    } catch (error) {
      console.error("Failed to fetch history", error);
    }
  };

  const fetchAnalyzedMatches = async () => {
    try {
      const res = await fetch(`${API_URL}/api/analyzed-matches`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setAnalyzedMatches(data);
      }
    } catch (error) {
      console.error("Failed to fetch analyzed matches", error);
    }
  };

  const runDailyAnalysis = async () => {
    setAnalyzingDaily(true);
    try {
      const res = await fetch(`${API_URL}/api/daily-analysis`);
      const data = await res.json();
      alert(data.message);
      fetchAnalyzedMatches();
    } catch (error) {
      console.error("Failed to run daily analysis", error);
      alert("Failed to run daily analysis");
    } finally {
      setAnalyzingDaily(false);
    }
  };

  const updateResults = async () => {
    setUpdatingResults(true);
    try {
      const res = await fetch(`${API_URL}/api/update-results`);
      const data = await res.json();
      alert(data.message);
      fetchHistory();
    } catch (error) {
      console.error("Failed to update results", error);
    } finally {
      setUpdatingResults(false);
    }
  };

  const toggleMatchSelection = (matchId: string) => {
    setSelectedMatches(prev =>
      prev.includes(matchId)
        ? prev.filter(id => id !== matchId)
        : [...prev, matchId]
    );
  };

  const buildSlipFromSelection = async () => {
    if (selectedMatches.length === 0) {
      alert("Please select at least one match");
      return;
    }
    
    setLoading(true);
    setCurrentSlip(null);
    try {
      const res = await fetch(`${API_URL}/api/build-slip-from-selection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          selected_matches: selectedMatches,
          target_odds: targetOdds,
          risk_profile: riskProfile
        }),
      });
      const data = await res.json();
      setCurrentSlip(data);
      setSelectedMatches([]);
      setShowBrowseMatches(false);
      fetchHistory();
      fetchAnalyzedMatches();
    } catch (error) {
      console.error("Error generating slip", error);
      alert("Failed to generate slip");
    } finally {
      setLoading(false);
    }
  };

  const generateSlip = async () => {
    setLoading(true);
    setCurrentSlip(null);
    try {
      const res = await fetch(`${API_URL}/api/build-accumulator`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          target_odds: targetOdds, 
          risk_profile: riskProfile,
          start_date: new Date().toISOString().split('T')[0],
          end_date: new Date().toISOString().split('T')[0]
        }),
      });
      const data = await res.json();
      setCurrentSlip(data);
      fetchHistory();
    } catch (error) {
      console.error("Error generating slip", error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopySuccess(id);
    setTimeout(() => setCopySuccess(null), 2000);
  };

  const toggleSlipExpand = (slipId: string) => {
    setExpandedSlips(prev => {
      const newSet = new Set(prev);
      if (newSet.has(slipId)) {
        newSet.delete(slipId);
      } else {
        newSet.add(slipId);
      }
      return newSet;
    });
  };

  // Group history by slip_id
  const groupedHistory = history.reduce((acc: Record<string, GroupedSlip>, pick) => {
    const slipId = pick.slip_id;
    if (!acc[slipId]) {
      acc[slipId] = {
        slip_id: slipId,
        picks: [],
        target_odds: pick.target_odds,
        risk_profile: pick.risk_profile,
        date_generated: pick.created_at,
        status: pick.status
      };
    }
    acc[slipId].picks.push(pick);
    return acc;
  }, {});

  const slipsArray: GroupedSlip[] = Object.values(groupedHistory).reverse();

  // Calculate overall slip status
  const getSlipStatus = (picks: Prediction[]) => {
    const allSettled = picks.every(p => p.status === "WON" || p.status === "LOST");
    if (!allSettled) return "PENDING";
    
    const allWon = picks.every(p => p.status === "WON");
    return allWon ? "WON" : "LOST";
  };

  // Calculate Dashboard Stats
  const settledSlips = slipsArray.filter(slip => {
    const status = getSlipStatus(slip.picks);
    return status === "WON" || status === "LOST";
  });
  
  const wonSlips = settledSlips.filter(slip => getSlipStatus(slip.picks) === "WON").length;
  const winRate = settledSlips.length > 0 ? Math.round((wonSlips / settledSlips.length) * 100) : 0;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8 font-sans selection:bg-emerald-500/30">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header & Stats */}
        <header className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                SportyBot Pro
              </h1>
              <p className="text-zinc-400 mt-1">Institutional-Grade AI Betting Intelligence</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowBrowseMatches(!showBrowseMatches)}
                className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 px-4 py-2 rounded-lg text-sm font-medium transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                {showBrowseMatches ? "Hide Matches" : "Browse Matches"}
              </button>
              <button
                onClick={runDailyAnalysis}
                disabled={analyzingDaily}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
              >
                <svg className={`w-4 h-4 ${analyzingDaily ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {analyzingDaily ? "Analyzing..." : "Daily Analysis"}
              </button>
              <button
                onClick={updateResults}
                disabled={updatingResults}
                className="flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
              >
                <svg className={`w-4 h-4 ${updatingResults ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {updatingResults ? "Checking..." : "Update Results"}
              </button>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-zinc-900/50 backdrop-blur border border-zinc-800 p-5 rounded-xl">
              <p className="text-zinc-500 text-sm font-medium uppercase tracking-wider">Verified Win Rate</p>
              <p className={`text-3xl font-bold mt-1 ${winRate >= 75 ? 'text-emerald-400' : winRate >= 50 ? 'text-amber-400' : 'text-zinc-300'}`}>
                {winRate}%
              </p>
              <p className="text-zinc-600 text-xs mt-1">Based on {settledSlips.length} settled slips</p>
            </div>
            <div className="bg-zinc-900/50 backdrop-blur border border-zinc-800 p-5 rounded-xl">
              <p className="text-zinc-500 text-sm font-medium uppercase tracking-wider">Total Slips</p>
              <p className="text-3xl font-bold text-zinc-100 mt-1">{slipsArray.length}</p>
              <p className="text-zinc-600 text-xs mt-1">Across all risk profiles</p>
            </div>
            <div className="bg-zinc-900/50 backdrop-blur border border-zinc-800 p-5 rounded-xl">
              <p className="text-zinc-500 text-sm font-medium uppercase tracking-wider">Active Engine</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                <p className="text-emerald-400 font-semibold">Llama-3.3-70B Online</p>
              </div>
            </div>
          </div>
        </header>

        {/* Browse Analyzed Matches */}
        {showBrowseMatches && (
          <section className="bg-zinc-900/80 backdrop-blur border border-emerald-500/30 p-6 rounded-2xl shadow-2xl">
            <h2 className="text-xl font-semibold mb-6 text-zinc-100 flex items-center gap-2">
              <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Browse Analyzed Matches ({analyzedMatches.length})
            </h2>
            
            {analyzedMatches.length === 0 ? (
              <div className="text-center py-8 border-2 border-dashed border-zinc-700 rounded-xl">
                <p className="text-zinc-400 mb-2">No analyzed matches yet</p>
                <p className="text-sm text-zinc-500">Click "Daily Analysis" to analyze today's fixtures</p>
              </div>
            ) : (
              <div className="space-y-3">
                {analyzedMatches.map((match) => (
                  <div 
                    key={match.id} 
                    className={`group p-4 rounded-xl border transition-all cursor-pointer ${
                      selectedMatches.includes(match.id)
                        ? 'bg-emerald-950/30 border-emerald-500/50'
                        : 'bg-zinc-950/50 hover:bg-zinc-800/50 border-zinc-800 hover:border-zinc-700'
                    }`}
                    onClick={() => toggleMatchSelection(match.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-1 w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${
                        selectedMatches.includes(match.id)
                          ? 'bg-emerald-500 border-emerald-500'
                          : 'border-zinc-600'
                      }`}>
                        {selectedMatches.includes(match.id) && (
                          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">
                            {match.selected_market}
                          </span>
                          <span className="text-[10px] text-zinc-500">{match.league}</span>
                        </div>
                        <p className="text-base font-semibold text-zinc-100 mb-2 break-words">
                          {match.match_name}
                        </p>
                        <div className="flex items-center gap-4 text-xs">
                          <div>
                            <span className="text-zinc-500">Odds:</span>
                            <span className="text-emerald-400 font-bold ml-1">{match.estimated_odds}</span>
                          </div>
                          <div>
                            <span className="text-zinc-500">Confidence:</span>
                            <span className="text-cyan-400 font-bold ml-1">{match.confidence}%</span>
                          </div>
                        </div>
                        {match.reasoning && (
                          <p className="text-xs text-zinc-400 italic mt-2 break-words">
                            "{match.reasoning}"
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                
                {selectedMatches.length > 0 && (
                  <div className="pt-4 border-t border-zinc-800">
                    <div className="flex items-center justify-between mb-4">
                      <p className="text-sm text-zinc-400">
                        {selectedMatches.length} match{selectedMatches.length !== 1 ? 'es' : ''} selected
                      </p>
                      <button
                        onClick={buildSlipFromSelection}
                        disabled={loading}
                        className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white font-semibold py-2 px-6 rounded-lg transition-all"
                      >
                        {loading ? "Building Slip..." : "Build Slip from Selection"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* Generator Section */}
        <section className="bg-zinc-900/80 backdrop-blur border border-zinc-800 p-6 rounded-2xl shadow-2xl">
          <h2 className="text-xl font-semibold mb-6 text-zinc-100 flex items-center gap-2">
            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Build Accumulator
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
            <div className="md:col-span-4">
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wider">Target Odds</label>
              <input
                type="number"
                step="0.1"
                value={targetOdds}
                onChange={(e) => setTargetOdds(parseFloat(e.target.value))}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
              />
            </div>
            <div className="md:col-span-4">
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wider">Risk Profile</label>
              <select
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all appearance-none"
              >
                <option value="safe">Safe (High Confidence, Lower Odds)</option>
                <option value="balanced">Balanced (Medium Risk, Medium Reward)</option>
                <option value="aggressive">Aggressive (High Value, Higher Risk)</option>
              </select>
            </div>
            <div className="md:col-span-4">
              <button
                onClick={generateSlip}
                disabled={loading}
                className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white font-semibold py-2.5 px-6 rounded-lg transition-all shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Analyzing Markets...
                  </>
                ) : (
                  "Generate Slip"
                )}
              </button>
            </div>
          </div>
        </section>

        {/* Current Slip Display */}
        {currentSlip && (
          <section className="bg-zinc-900/80 backdrop-blur border border-emerald-500/30 p-6 rounded-2xl shadow-2xl shadow-emerald-900/10">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
              <div>
                <h2 className="text-xl font-bold text-emerald-400 flex items-center gap-2">
                  <span className="bg-emerald-500/10 px-2 py-0.5 rounded text-sm border border-emerald-500/20">
                    {currentSlip.risk_profile.toUpperCase()}
                  </span>
                  Slip ID: {currentSlip.slip_id}
                </h2>
                <p className="text-zinc-400 text-sm mt-1">{currentSlip.number_of_legs} Legs • Target: {currentSlip.target_odds}x</p>
              </div>
              <div className="text-right bg-zinc-950 px-6 py-3 rounded-xl border border-zinc-800">
                <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold">Total Odds</p>
                <p className="text-3xl font-bold text-white">{currentSlip.actual_odds}</p>
              </div>
            </div>

            <div className="space-y-3">
              {currentSlip.picks.map((pick: any, index: number) => (
                <div key={index} className="group bg-zinc-950/50 hover:bg-zinc-800/50 p-4 rounded-xl border border-zinc-800 hover:border-zinc-700 transition-all">
                  <div className="flex flex-col gap-3">
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded flex-shrink-0">
                        {pick.selected_market}
                      </span>
                      <span className="text-[10px] text-zinc-500">{pick.league}</span>
                    </div>
                    <p className="text-base font-semibold text-zinc-100 break-words">
                      {pick.match_name}
                    </p>
                    <div className="flex items-center gap-6 justify-between md:justify-end">
                      <div className="text-center">
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Odds</p>
                        <p className="text-xl font-bold text-emerald-400">{pick.estimated_odds}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Conf.</p>
                        <p className="text-xl font-bold text-cyan-400">{pick.confidence}%</p>
                      </div>
                      <button
                        onClick={() => copyToClipboard(pick.match_name, `copy-${index}`)}
                        className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs font-medium py-2 px-4 rounded-lg transition-all border border-zinc-700"
                      >
                        {copySuccess === `copy-${index}` ? "Copied!" : "Copy Match"}
                      </button>
                    </div>
                    {pick.reasoning && (
                      <div className="mt-3 pt-3 border-t border-zinc-800/50">
                        <p className="text-xs text-zinc-400 italic break-words">"{pick.reasoning}"</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-6 p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 018 0z" />
              </svg>
              <div>
                <p className="text-sm font-semibold text-amber-200">Manual Entry Required</p>
                <p className="text-xs text-amber-200/70 mt-1">
                  Open your bookmaker, paste the copied match names, and select the exact markets shown above.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* History Section */}
        <section className="bg-zinc-900/80 backdrop-blur border border-zinc-800 p-6 rounded-2xl shadow-2xl">
          <h2 className="text-xl font-semibold mb-6 text-zinc-100 flex items-center gap-2">
            <svg className="w-5 h-5 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Prediction History
          </h2>
          
          {slipsArray.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-zinc-800 rounded-xl">
              <p className="text-zinc-500">No history yet. Generate your first slip to start tracking accuracy.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {slipsArray.map((slip: GroupedSlip) => {
                const slipStatus = getSlipStatus(slip.picks);
                const isExpanded = expandedSlips.has(slip.slip_id);
                const totalOdds = slip.picks.reduce((acc: number, pick: Prediction) => acc * (pick.estimated_odds || 1), 1).toFixed(2);
                
                return (
                  <div key={slip.slip_id} className="bg-zinc-950/50 border border-zinc-800 rounded-xl overflow-hidden">
                    <div 
                      onClick={() => toggleSlipExpand(slip.slip_id)}
                      className="p-4 cursor-pointer hover:bg-zinc-800/30 transition-colors"
                    >
                      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
                        <div className="flex items-center gap-3 flex-1">
                          <button className="text-zinc-400 hover:text-zinc-200 transition-colors">
                            <svg 
                              className={`w-5 h-5 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
                              fill="none" 
                              viewBox="0 0 24 24" 
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-mono text-sm font-bold text-zinc-300">{slip.slip_id}</span>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                slipStatus === "WON" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                                slipStatus === "LOST" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                                "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              }`}>
                                {slipStatus}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-500">
                              {slip.picks.length} Legs • {slip.risk_profile} • {new Date(slip.date_generated).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        
                        <div className="ml-8">
                          <div className="text-right">
                            <p className="text-[10px] text-zinc-500 uppercase">Actual Odds</p>
                            <p className={`text-lg font-bold ${slipStatus === 'WON' ? 'text-emerald-400' : 'text-zinc-100'}`}>
                              {totalOdds}x
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-zinc-800 bg-zinc-900/30 p-4 space-y-2">
                        {slip.picks.map((pick: Prediction, idx: number) => (
                          <div key={idx} className="flex items-center justify-between p-3 bg-zinc-950/50 rounded-lg border border-zinc-800">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-emerald-400">{pick.selected_market}</span>
                                <span className="text-xs text-zinc-500">•</span>
                                <span className="text-xs text-zinc-500">{pick.league}</span>
                              </div>
                              <p className="text-sm font-medium text-zinc-200 break-words">
                                {pick.match_name}
                              </p>
                              {pick.match_date && (
                                <p className="text-xs text-zinc-500 mt-1">
                                  {new Date(pick.match_date).toLocaleDateString('en-US', { 
                                    weekday: 'short', 
                                    month: 'short', 
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                  })}
                                </p>
                              )}
                              {pick.actual_result && (
                                <p className="text-xs text-zinc-400 mt-1">Final Score: {pick.actual_result}</p>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-4 ml-4">
                              <div className="text-right">
                                <p className="text-[10px] text-zinc-500 uppercase">Odds</p>
                                <p className="text-sm font-bold text-emerald-400">{pick.estimated_odds}</p>
                              </div>
                              <div className="text-right">
                                <p className="text-[10px] text-zinc-500 uppercase">Conf</p>
                                <p className="text-sm font-bold text-cyan-400">{pick.confidence}%</p>
                              </div>
                              
                              <div className="flex-shrink-0 ml-2">
                                {pick.status === "WON" ? (
                                  <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                  </svg>
                                ) : pick.status === "LOST" ? (
                                  <svg className="w-6 h-6 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

      </div>
    </main>
  );
}