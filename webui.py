import json
import os
import sys
import subprocess
import threading
import webbrowser
from collections import deque
from flask import Flask, request, jsonify

try:
    import psutil
except ImportError:
    psutil = None

app = Flask(__name__)
CONFIG_PATH = "config.json"

log_queue = deque(maxlen=300)
scheduler_process = None
process_lock = threading.Lock()

def process_reader(proc):
    buffer = ""
    while True:
        try:
            char = proc.stdout.read(1)
            if not char:
                break
            
            if char == '\n':
                log_queue.append(buffer)
                buffer = ""
            elif char == '\r':
                if buffer:
                    if len(log_queue) > 0 and log_queue[-1].startswith("~P~"):
                        log_queue[-1] = "~P~" + buffer
                    else:
                        log_queue.append("~P~" + buffer)
                buffer = ""
            else:
                buffer += char
        except Exception:
            break
            
    if buffer:
        log_queue.append(buffer)

def run_scheduler_task():
    global scheduler_process
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_scheduler.py")
    
    try:
        scheduler_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        process_reader(scheduler_process)
        scheduler_process.wait()
    except Exception as e:
        log_queue.append(f"[Web UI 内部错误] {e}")
    finally:
        with process_lock:
            scheduler_process = None
        log_queue.append("[Web UI] 调度器进程已退出。")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CPA 自动调度管理台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: #1e293b;
            min-height: 100vh;
        }
        .glass-panel {
            background: rgba(255, 255, 255, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.8);
            border-radius: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.025);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .glass-panel:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);
        }
        .input-field {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #cbd5e1;
            color: #334155;
            border-radius: 0.5rem;
            padding: 0.5rem 0.75rem;
            width: 100%;
            transition: all 0.3s ease;
        }
        .input-field:focus {
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }
        .checkbox-custom {
            accent-color: #6366f1;
            width: 1.25rem;
            height: 1.25rem;
            cursor: pointer;
        }
        .btn-primary {
            background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
            color: white;
            font-weight: 600;
            padding: 0.75rem 2rem;
            border-radius: 9999px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
            border: none;
        }
        .btn-primary:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
        }
        .btn-primary:active {
            transform: translateY(1px);
        }
        .btn-success {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        .btn-danger {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }
        .group-title {
            background: linear-gradient(to right, #2563eb, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        /* Log container styling */
        #log-container {
            background: #0f172a;
            color: #10b981;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.3);
        }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.05); border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.25); }
    </style>
</head>
<body class="p-6 md:p-10 overflow-x-hidden">
    <div id="app" class="max-w-6xl mx-auto" v-cloak>
        <div class="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
            <div>
                <h1 class="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600 pb-2">
                    CPA 自动调度中心
                </h1>
                <p class="text-slate-500 font-medium">配置面板与实时任务监控台 · 修改即生效</p>
            </div>
            <div class="flex gap-4 items-center">
                <button @click="saveConfig" class="btn-primary flex items-center gap-2 px-6 py-2.5">
                    <svg v-if="saving" class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    <svg v-else-if="saved" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    <svg v-else class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/></svg>
                    <span>{{ saving ? '保存中...' : (saved ? '已保存！' : '保存配置') }}</span>
                </button>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- 运行监控面板 -->
            <div class="glass-panel p-6 lg:col-span-2 flex flex-col shadow-lg border-2 border-slate-100">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-2xl font-bold flex items-center gap-2 group-title">
                        <svg class="h-6 w-6 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                        实时执行日志与终端控制
                    </h2>
                    <div class="flex items-center gap-3">
                        <span class="flex items-center gap-2 text-sm font-semibold" :class="running ? 'text-green-600' : 'text-slate-400'">
                            <span class="relative flex h-3 w-3">
                              <span v-if="running" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                              <span class="relative inline-flex rounded-full h-3 w-3" :class="running ? 'bg-green-500' : 'bg-slate-300'"></span>
                            </span>
                            状态: {{ running ? '调度器运行中...' : '已停止' }}
                        </span>
                        
                        <button v-if="!running" @click="startProcess" :disabled="processSubmitting" class="btn-primary btn-success py-1.5 px-5 text-sm rounded-lg shadow-md hover:shadow-lg focus:outline-none transition-all flex items-center gap-1">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                            启动调度
                        </button>
                        <button v-else @click="stopProcess" :disabled="processSubmitting" class="btn-primary btn-danger py-1.5 px-5 text-sm rounded-lg shadow-md hover:shadow-lg focus:outline-none transition-all flex items-center gap-1">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10h6v4H9z"/></svg>
                            终止调度
                        </button>
                    </div>
                </div>
                
                <div id="log-container" class="rounded-xl p-4 h-72 overflow-y-auto text-sm">
                    <div v-for="(line, idx) in logs" :key="idx" class="whitespace-pre-wrap leading-relaxed tracking-tight">{{ line }}</div>
                    <div v-if="logs.length === 0" class="text-slate-500 italic mt-2 ml-2 tracking-wide font-sans">点击右上角"启动调度"开始运行...</div>
                </div>
            </div>

            <!-- 基础与调度配置 -->
            <div class="glass-panel p-6">
                <h2 class="text-xl font-bold mb-5 flex items-center gap-2 group-title">
                    <svg class="h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    基础任务与网络策略
                </h2>
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">检查间隔 (秒)</label>
                            <input type="number" v-model.number="config.check_interval_seconds" class="input-field" title="调度器主动轮询的周期（默认 3600 秒=1小时）">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">自动预警阈值</label>
                            <input type="number" v-model.number="config.account_threshold" class="input-field" title="低于该值将自动启动账号注册补充">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">执行脚本名称</label>
                            <input type="text" v-model="config.register_script" class="input-field" title="调度器启动的脚本文件">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">全局 HTTP 代理</label>
                            <input type="text" v-model="config.proxy" placeholder="如 http://127.0.0.1:7890" class="input-field">
                        </div>
                    </div>
                </div>
            </div>

            <!-- 数据探测与注册策略 -->
            <div class="glass-panel p-6">
                <h2 class="text-xl font-bold mb-5 flex items-center gap-2 group-title">
                    <svg class="h-5 w-5 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                    资源探测与注册工作流
                </h2>
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">单次拉起注册数量</label>
                            <input type="number" v-model.number="config.total_accounts" class="input-field" title="实际会使用缺口与此值的最大值">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">并行池大小 (Workers)</label>
                            <input type="number" v-model.number="config.max_workers" class="input-field">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">最大随机探测数</label>
                            <input type="number" v-model.number="config.probe_max_count" class="input-field" title="设为 0 代表全量探测">
                        </div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">网络探测并发</label><input type="number" v-model.number="config.probe_workers" class="input-field"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">单次探测超时 (s)</label><input type="number" v-model.number="config.probe_timeout" class="input-field"></div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">连通性预检</label>
                            <select v-model="config.preflight" class="input-field">
                                <option value="y">开启 (y)</option>
                                <option value="n">禁用 (n)</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 邮箱服务配置 -->
            <div class="glass-panel p-6">
                <h2 class="text-xl font-bold mb-5 flex items-center gap-2 group-title">
                    <svg class="h-5 w-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    接码邮箱上游源
                </h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-slate-600 mb-1">主要服务商 (mail_provider)</label>
                        <select v-model="config.mail_provider" class="input-field border-orange-200 bg-orange-50/50">
                            <option value="lamail">LaMail 体系</option>
                            <option value="duckmail">DuckMail 体系</option>
                            <option value="cfmail">Cloudflare (CFMail) 体系</option>
                            <option value="tempmail_lol">TempMail.lol 体系</option>
                        </select>
                    </div>

                    <div v-if="config.mail_provider === 'lamail'" class="p-4 bg-white rounded-lg border border-slate-200 space-y-3 relative overflow-hidden shadow-sm">
                        <div class="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">API 地址</label><input type="text" v-model="config.lamail_api_base" class="input-field"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">API Key</label><input type="password" v-model="config.lamail_api_key" class="input-field"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">自定义 Domain</label><input type="text" v-model="config.lamail_domain" class="input-field"></div>
                    </div>
                    
                    <div v-if="config.mail_provider === 'cfmail'" class="p-4 bg-white rounded-lg border border-slate-200 space-y-3 relative overflow-hidden shadow-sm">
                        <div class="absolute top-0 left-0 w-1 h-full bg-orange-500"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">CF 配置路径</label><input type="text" v-model="config.cfmail_config_path" class="input-field"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">使用账号配置段 (profile)</label><input type="text" v-model="config.cfmail_profile" class="input-field"></div>
                    </div>

                    <div v-if="config.mail_provider === 'duckmail'" class="p-4 bg-white rounded-lg border border-slate-200 space-y-3 relative overflow-hidden shadow-sm">
                        <div class="absolute top-0 left-0 w-1 h-full bg-yellow-500"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">API 地址</label><input type="text" v-model="config.duckmail_api_base" class="input-field"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">Bearer Token</label><input type="password" v-model="config.duckmail_bearer" class="input-field"></div>
                    </div>

                    <div v-if="config.mail_provider === 'tempmail_lol'" class="p-4 bg-white rounded-lg border border-slate-200 space-y-3 relative overflow-hidden shadow-sm">
                        <div class="absolute top-0 left-0 w-1 h-full bg-indigo-500"></div>
                        <div><label class="block text-sm font-semibold text-slate-600 mb-1">API 地址 (可选)</label><input type="text" v-model="config.tempmail_lol_api_base" class="input-field" placeholder="默认: https://api.tempmail.lol/v2"></div>
                    </div>
                </div>
            </div>

            <!-- CPA 数据中心 -->
            <div class="glass-panel p-6">
                <h2 class="text-xl font-bold mb-4 flex items-center gap-2 group-title">
                    <svg class="h-5 w-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                    分布式 CPA 通讯网关
                </h2>
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div class="col-span-2">
                            <label class="block text-sm font-semibold text-slate-600 mb-1">上报中枢 API (upload_api_url)</label>
                            <input type="text" v-model="config.upload_api_url" class="input-field font-mono text-sm">
                        </div>
                        <div class="col-span-2">
                            <label class="block text-sm font-semibold text-slate-600 mb-1">鉴权 Token (upload_api_token)</label>
                            <input type="password" v-model="config.upload_api_token" class="input-field font-mono text-sm">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">触发频率: 每隔N个</label>
                            <input type="number" v-model.number="config.cpa_upload_every_n" class="input-field">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-600 mb-1">探测器前置清理</label>
                            <select v-model="config.cpa_cleanup" class="input-field">
                                <option value="y">启用清理 (y)</option>
                                <option value="n">禁用，依靠调度引擎 (n)</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <script>
        const { createApp, ref, onMounted } = Vue;
        createApp({
            setup() {
                const config = ref({
                    total_accounts: 300,
                    account_threshold: 10000,
                    probe_max_count: 1000,
                    check_interval_seconds: 3600,
                    register_script: "ncs_register.py",
                    preflight: "n",
                    cpa_cleanup: "n",
                    max_workers: 3,
                    probe_workers: 12,
                    probe_timeout: 10,
                    mail_provider: 'lamail',
                    tempmail_lol_api_base: 'https://api.tempmail.lol/v2',
                    proxy: ''
                });
                const saving = ref(false);
                const saved = ref(false);
                const running = ref(false);
                const logs = ref([]);
                const processSubmitting = ref(false);

                const loadConfig = async () => {
                    try {
                        const res = await fetch("/api/config");
                        const data = await res.json();
                        config.value = { ...config.value, ...data };
                    } catch(e) { console.error('载入配置失败', e); }
                };

                const saveConfig = async () => {
                    saving.value = true;
                    try {
                        await fetch("/api/config", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(config.value)
                        });
                        saving.value = false;
                        saved.value = true;
                        setTimeout(() => saved.value = false, 2000);
                    } catch(e) {
                        saving.value = false;
                        alert('保存失败！');
                    }
                };
                
                let isUserScrollingView = false;
                
                const startPolling = () => {
                    const container = document.getElementById("log-container");
                    if(container) {
                        container.addEventListener('scroll', () => {
                            const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 50;
                            isUserScrollingView = !isAtBottom;
                        });
                    }
                    
                    setInterval(async () => {
                        try {
                            const res = await fetch("/api/logs");
                            const data = await res.json();
                            logs.value = data.logs;
                            running.value = data.running;
                            
                            if (container && !isUserScrollingView) {
                                // 使得 DOM 更新后再次计算滚动位置
                                setTimeout(() => {
                                    container.scrollTop = container.scrollHeight;
                                }, 50);
                            }
                        } catch(e) {}
                    }, 800);
                };

                const startProcess = async () => {
                    processSubmitting.value = true;
                    await saveConfig();
                    await fetch("/api/start", { method: "POST" });
                    processSubmitting.value = false;
                };

                const stopProcess = async () => {
                    if(!confirm("确定要强行终止该调度进程吗？所有的注册工作都会被中断。")) return;
                    processSubmitting.value = true;
                    await fetch("/api/stop", { method: "POST" });
                    setTimeout(() => processSubmitting.value = false, 1000);
                };

                onMounted(() => {
                    loadConfig();
                    startPolling();
                });
                
                return { 
                    config, saveConfig, saving, saved, 
                    running, logs, startProcess, stopProcess, processSubmitting 
                };
            }
        }).mount('#app');
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_TEMPLATE 

@app.route("/api/logs")
def get_logs():
    return jsonify({
        "logs": [l[3:] if str(l).startswith("~P~") else l for l in log_queue],
        "running": scheduler_process is not None
    })

@app.route("/api/start", methods=["POST"])
def start_process():
    global scheduler_process
    with process_lock:
        if scheduler_process is not None:
            return jsonify({"success": False, "msg": "调度器已在运行中"})
        log_queue.append("[Web UI] ⚡ 正在启动后台调度引擎...")
        threading.Thread(target=run_scheduler_task, daemon=True).start()
    return jsonify({"success": True})

@app.route("/api/stop", methods=["POST"])
def stop_process():
    global scheduler_process
    with process_lock:
        if scheduler_process is not None:
            try:
                if psutil:
                    parent = psutil.Process(scheduler_process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                else:
                    scheduler_process.terminate()
            except Exception as e:
                log_queue.append(f"[Web UI] 终止失败: {e}")
            log_queue.append("[Web UI] 🛑 发送强制停止指令...")
    return jsonify({"success": True})

@app.route("/api/config", methods=["GET"])
def get_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({})

@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json
    current = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            pass
    
    current.update(data)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[Web UI] 启动中，将在浏览器打开界面... 端口: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
