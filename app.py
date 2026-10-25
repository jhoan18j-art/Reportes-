<!DOCTYPE html>
<html lang="es" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Club Park Valet - Asistente IA</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Inter Font -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'sans-serif'] },
                    colors: {
                        brand: {
                            50: '#f0fdf4',
                            100: '#dcfce7',
                            500: '#22c55e',
                            600: '#16a34a',
                            700: '#15803d',
                            900: '#14532d',
                        },
                        darkCard: '#1e293b'
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="bg-slate-100 text-slate-800 h-full flex flex-col selection:bg-brand-500 selection:text-white">

    <!-- Notificación flotante (Mensaje de alerta personalizado) -->
    <div id="toast" class="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 transition-all duration-300 opacity-0 pointer-events-none flex items-center gap-3 bg-slate-900 text-white px-5 py-3 rounded-2xl shadow-xl border border-slate-700 text-sm max-w-sm w-[90%]">
        <i id="toastIcon" class="fa-solid fa-circle-check text-brand-500 text-lg"></i>
        <span id="toastMsg" class="truncate">Operación realizada con éxito</span>
    </div>

    <!-- Header Móvil Superior -->
    <header class="bg-slate-900 text-white sticky top-0 z-40 px-4 py-3 shadow-md flex items-center justify-between">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-brand-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-brand-500/30">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div>
                <h1 class="font-bold text-base leading-tight">Club Park AI</h1>
                <p class="text-xs text-slate-400">Asistente Operativo Inteligente</p>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="app.syncData()" class="w-9 h-9 rounded-xl bg-slate-800 text-slate-300 hover:text-white flex items-center justify-center transition active:scale-95" title="Sincronizar">
                <i id="syncIcon" class="fa-solid fa-rotate"></i>
            </button>
            <div class="w-8 h-8 rounded-full bg-brand-600/30 border border-brand-500 text-brand-400 text-xs font-bold flex items-center justify-center">
                JH
            </div>
        </div>
    </header>

    <!-- Contenedor Principal (Vistas Tab) -->
    <main class="flex-1 overflow-y-auto pb-24 px-4 pt-4 max-w-lg mx-auto w-full flex flex-col">

        <!-- VISTA 1: ASISTENTE IA (Chat Estilo Aeroman) -->
        <section id="view-assistant" class="flex-1 flex flex-col space-y-4">
            <!-- Banner de Bienvenida Asistente -->
            <div class="bg-gradient-to-r from-slate-900 to-slate-800 text-white p-4 rounded-2xl shadow-sm border border-slate-700/50 flex items-center justify-between">
                <div>
                    <span class="bg-brand-500/20 text-brand-400 border border-brand-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider mb-1 inline-block">Sistema Activo</span>
                    <h2 class="font-bold text-base">Hola, Jonathan o Héctor</h2>
                    <p class="text-xs text-slate-300">Escribe o usa los comandos rápidos abajo.</p>
                </div>
                <div class="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 text-xl">
                    <i class="fa-solid fa-terminal"></i>
                </div>
            </div>

            <!-- Chips de Comandos Rápidos -->
            <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
                <button onclick="app.runCommand('Registrar auto placas ABC-123 en San Ángel')" class="bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded-xl text-xs font-semibold shrink-0 shadow-sm transition active:scale-95 flex items-center gap-1.5">
                    <i class="fa-solid fa-plus text-brand-600"></i> Registrar Placas ABC
                </button>
                <button onclick="app.runCommand('Buscar folio 101')" class="bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded-xl text-xs font-semibold shrink-0 shadow-sm transition active:scale-95 flex items-center gap-1.5">
                    <i class="fa-solid fa-magnifying-glass text-brand-600"></i> Buscar Folio 101
                </button>
                <button onclick="app.runCommand('Corte de caja')" class="bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded-xl text-xs font-semibold shrink-0 shadow-sm transition active:scale-95 flex items-center gap-1.5">
                    <i class="fa-solid fa-chart-pie text-brand-600"></i> Corte de Caja
                </button>
                <button onclick="app.runCommand('Ayuda')" class="bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded-xl text-xs font-semibold shrink-0 shadow-sm transition active:scale-95 flex items-center gap-1.5">
                    <i class="fa-solid fa-circle-question text-brand-600"></i> Ayuda
                </button>
            </div>

            <!-- Contenedor del Chat / Conversación -->
            <div id="chatContainer" class="flex-1 bg-white rounded-2xl p-4 border border-slate-200/80 shadow-sm space-y-4 overflow-y-auto max-h-[380px] min-h-[300px]">
                <!-- Mensajes inyectados dinámicamente -->
            </div>

            <!-- Barra de Entrada de Comandos IA -->
            <form id="chatForm" onsubmit="app.handleChatSubmit(event)" class="flex gap-2 bg-white p-2 rounded-2xl border border-slate-200 shadow-sm">
                <input type="text" id="chatInput" placeholder="Ej. Registrar auto placas XYZ-98 en Polanco..." class="flex-1 bg-transparent px-3 py-2 text-sm text-slate-800 focus:outline-none font-medium">
                <button type="submit" class="bg-brand-600 hover:bg-brand-700 text-white w-10 h-10 rounded-xl flex items-center justify-center transition shadow-md shadow-brand-600/30 active:scale-95">
                    <i class="fa-solid fa-paper-plane text-sm"></i>
                </button>
            </form>
        </section>

        <!-- VISTA 2: OPERACIONES Y VEHÍCULOS (En Tiempo Real) -->
        <section id="view-operations" class="space-y-4 hidden">
            <!-- Estadísticas Operativas -->
            <div class="grid grid-cols-2 gap-3">
                <div class="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
                        <i class="fa-solid fa-car"></i>
                    </div>
                    <div>
                        <p class="text-xs text-slate-400 font-medium">En Patio</p>
                        <h3 id="statParked" class="text-lg font-bold text-slate-800">0</h3>
                    </div>
                </div>
                <div class="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                        <i class="fa-solid fa-flag-checkered"></i>
                    </div>
                    <div>
                        <p class="text-xs text-slate-400 font-medium">Entregados</p>
                        <h3 id="statDelivered" class="text-lg font-bold text-slate-800">0</h3>
                    </div>
                </div>
            </div>

            <!-- Filtros de Sucursal y Búsqueda -->
            <div class="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm space-y-3">
                <div class="relative">
                    <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400"><i class="fa-solid fa-magnifying-glass text-sm"></i></span>
                    <input type="text" id="searchInput" oninput="app.renderTickets()" placeholder="Buscar por placas o folio..." class="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-brand-500 transition">
                </div>
                <div class="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1" id="filterChips">
                    <button onclick="app.setFilter('todos')" class="filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white shrink-0 transition">Todos</button>
                    <button onclick="app.setFilter('San Ángel')" class="filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 shrink-0 transition">San Ángel</button>
                    <button onclick="app.setFilter('Polanco')" class="filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 shrink-0 transition">Polanco</button>
                    <button onclick="app.setFilter('Santa Fe')" class="filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 shrink-0 transition">Santa Fe</button>
                </div>
            </div>

            <!-- Lista Dinámica de Tickets -->
            <div id="ticketsContainer" class="space-y-3">
                <!-- Se inyecta con JS -->
            </div>
        </section>

        <!-- VISTA 3: NUEVO REGISTRO MANUAL -->
        <section id="view-new" class="space-y-4 hidden">
            <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-200/80">
                <h2 class="font-bold text-slate-900 text-lg mb-4 flex items-center gap-2">
                    <i class="fa-solid fa-ticket text-brand-600"></i> Ingreso de Vehículo
                </h2>
                <form id="checkinForm" onsubmit="app.handleManualCheckin(event)" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Sucursal</label>
                        <select id="sucursal" required class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-3 text-slate-800 font-medium text-sm focus:outline-none focus:border-brand-500">
                            <option value="San Ángel">San Ángel - Corporativo</option>
                            <option value="Polanco">Polanco - Masaryk</option>
                            <option value="Santa Fe">Santa Fe - Centro Comercial</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Folio</label>
                            <input type="text" id="folio" required placeholder="Ej. 102" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-3 text-slate-800 font-medium text-sm focus:outline-none focus:border-brand-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Placas</label>
                            <input type="text" id="placas" required placeholder="ABC-123" class="w-full uppercase bg-slate-50 border border-slate-200 rounded-xl px-3 py-3 text-slate-800 font-medium text-sm focus:outline-none focus:border-brand-500">
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Modelo y Color</label>
                        <input type="text" id="vehiculo" required placeholder="Ej. Audi A4 Gris" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-3 text-slate-800 font-medium text-sm focus:outline-none focus:border-brand-500">
                    </div>
                    <button type="submit" class="w-full bg-brand-600 hover:bg-brand-700 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-brand-600/30 transition flex items-center justify-center gap-2">
                        <i class="fa-solid fa-circle-check"></i> Registrar Ingreso
                    </button>
                </form>
            </div>
        </section>

    </main>

    <!-- Navegación Inferior (Tab Bar Móvil) -->
    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 z-40 max-w-lg mx-auto px-6 py-2 flex items-center justify-between shadow-2xl">
        <button onclick="app.switchTab('assistant')" id="tab-assistant" class="flex flex-col items-center gap-1 text-brand-600 transition">
            <i class="fa-solid fa-robot text-lg"></i>
            <span class="text-[10px] font-semibold">Asistente IA</span>
        </button>
        <button onclick="app.switchTab('operations')" id="tab-operations" class="flex flex-col items-center gap-1 text-slate-400 hover:text-slate-600 transition relative">
            <i class="fa-solid fa-list-check text-lg"></i>
            <span class="text-[10px] font-semibold">Operaciones</span>
            <span id="badgeCount" class="absolute -top-1 -right-2 bg-brand-500 text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center shadow-sm">0</span>
        </button>
        <button onclick="app.switchTab('new')" id="tab-new" class="flex flex-col items-center gap-1 text-slate-400 hover:text-slate-600 transition">
            <i class="fa-solid fa-circle-plus text-lg"></i>
            <span class="text-[10px] font-semibold">Nuevo</span>
        </button>
    </nav>

    <!-- Modal Detalle Ticket -->
    <div id="detailModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 hidden flex items-end sm:items-center justify-center p-0 sm:p-4">
        <div class="bg-white w-full max-w-md rounded-t-3xl sm:rounded-2xl p-6 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 class="font-bold text-slate-900 text-base" id="modalTitle">Detalle del Ticket</h3>
                <button onclick="app.closeModal()" class="w-8 h-8 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div id="modalContent" class="space-y-2 text-sm text-slate-600"></div>
            <div id="modalActions" class="pt-2 flex gap-3"></div>
        </div>
    </div>

    <!-- Script Principal Asistente Operativo -->
    <script>
        class ClubParkAssistantApp {
            constructor() {
                this.tickets = JSON.parse(localStorage.getItem('clubpark_ai_tickets')) || [
                    { id: '1', sucursal: 'San Ángel', folio: '101', placas: 'ABC-123', vehiculo: 'Mazda 3 Blanco', hora: '14:20', estado: 'estacionado' },
                    { id: '2', sucursal: 'Polanco', folio: '102', placas: 'XYZ-987', vehiculo: 'BMW Serie 3 Negro', hora: '15:05', estado: 'estacionado' }
                ];
                this.messages = JSON.parse(localStorage.getItem('clubpark_ai_msgs')) || [
                    { sender: 'ai', text: '¡Hola Jonathan y Héctor! Soy su Asistente Aeroman-IA para Club Park. ¿Qué operacion realizamos hoy? Escribe o pulsa un comando rápido.' }
                ];
                this.currentFilter = 'todos';
                this.activeTab = 'assistant';
                this.init();
            }

            init() {
                this.renderChat();
                this.renderTickets();
                this.updateStats();
            }

            showToast(msg, type = 'success') {
                const toast = document.getElementById('toast');
                document.getElementById('toastMsg').innerText = msg;
                document.getElementById('toastIcon').className = type === 'success' ? 'fa-solid fa-circle-check text-brand-500 text-lg' : 'fa-solid fa-circle-exclamation text-amber-500 text-lg';
                toast.classList.remove('opacity-0', 'pointer-events-none');
                toast.classList.add('opacity-100');
                setTimeout(() => {
                    toast.classList.remove('opacity-100');
                    toast.classList.add('opacity-0', 'pointer-events-none');
                }, 3000);
            }

            switchTab(tab) {
                this.activeTab = tab;
                ['assistant', 'operations', 'new'].forEach(t => {
                    const el = document.getElementById(`view-${t}`);
                    const btn = document.getElementById(`tab-${t}`);
                    if(t === tab) {
                        el.classList.remove('hidden');
                        btn.className = 'flex flex-col items-center gap-1 text-brand-600 transition';
                    } else {
                        el.classList.add('hidden');
                        btn.className = 'flex flex-col items-center gap-1 text-slate-400 hover:text-slate-600 transition';
                    }
                });
                if(tab === 'operations') this.renderTickets();
            }

            save() {
                localStorage.setItem('clubpark_ai_tickets', JSON.stringify(this.tickets));
                localStorage.setItem('clubpark_ai_msgs', JSON.stringify(this.messages));
                this.updateStats();
            }

            updateStats() {
                const parked = this.tickets.filter(t => t.estado === 'estacionado').length;
                const delivered = this.tickets.filter(t => t.estado === 'entregado').length;
                document.getElementById('statParked').innerText = parked;
                document.getElementById('statDelivered').innerText = delivered;
                document.getElementById('badgeCount').innerText = parked;
            }

            renderChat() {
                const container = document.getElementById('chatContainer');
                container.innerHTML = this.messages.map(m => {
                    if(m.sender === 'user') {
                        return `
                            <div class="flex justify-end">
                                <div class="bg-brand-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] text-sm shadow-sm font-medium">
                                    ${m.text}
                                </div>
                            </div>
                        `;
                    } else {
                        return `
                            <div class="flex items-start gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-slate-900 text-brand-400 flex items-center justify-center shrink-0 font-bold text-xs shadow">
                                    <i class="fa-solid fa-robot"></i>
                                </div>
                                <div class="bg-slate-50 border border-slate-200/80 text-slate-800 rounded-2xl rounded-tl-none px-4 py-3 max-w-[85%] text-sm shadow-sm space-y-1">
                                    <div class="font-bold text-[10px] text-brand-700 uppercase tracking-wide">Asistente IA</div>
                                    <div>${m.text}</div>
                                </div>
                            </div>
                        `;
                    }
                }).join('');
                container.scrollTop = container.scrollHeight;
            }

            handleChatSubmit(e) {
                e.preventDefault();
                const input = document.getElementById('chatInput');
                const val = input.value.trim();
                if(!val) return;
                input.value = '';
                this.runCommand(val);
            }

            runCommand(cmd) {
                this.messages.push({ sender: 'user', text: cmd });
                this.renderChat();

                // Procesamiento IA Inteligente (Simulado estilo Aeroman)
                const lower = cmd.toLowerCase();
                let response = "";

                if(lower.includes('registrar') || lower.includes('placas')) {
                    // Extraer placas o datos básicos
                    const placaMatch = cmd.match(/placas\s+([a-zA-Z0-9-]+)/i) || cmd.match(/([a-zA-Z]{3}-\d{3})/);
                    const placas = placaMatch ? placaMatch[1].toUpperCase() : 'AUT-' + Math.floor(Math.random() * 900 + 100);
                    const sucursal = lower.includes('polanco') ? 'Polanco' : lower.includes('santa fe') ? 'Santa Fe' : 'San Ángel';
                    const folio = Math.floor(Math.random() * 900 + 100).toString();

                    const nuevo = {
                        id: Date.now().toString(),
                        sucursal,
                        folio,
                        placas,
                        vehiculo: 'Vehículo Registrado por IA',
                        hora: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        estado: 'estacionado'
                    };
                    this.tickets.unshift(nuevo);
                    this.save();
                    response = `✅ <b>Ingreso registrado con éxito.</b><br>&bull; Folio: #${folio}<br>&bull; Placas: ${placas}<br>&bull; Sucursal: ${sucursal}<br>El vehículo ya se encuentra en el sistema activo.`;
                } 
                else if(lower.includes('buscar folio')) {
                    const folioMatch = cmd.match(/folio\s+(\d+)/i);
                    const fNum = folioMatch ? folioMatch[1] : '';
                    const found = this.tickets.find(t => t.folio === fNum);
                    if(found) {
                        response = `🔍 <b>Folio #${found.folio} Encontrado:</b><br>&bull; Placas: ${found.placas}<br>&bull; Sucursal: ${found.sucursal}<br>&bull; Estatus: <span class="uppercase font-bold">${found.estado}</span>`;
                    } else {
                        response = `⚠️ No se encontró ningún registro activo con el folio #${fNum}.`;
                    }
                }
                else if(lower.includes('corte') || lower.includes('caja')) {
                    const total = this.tickets.length;
                    const parked = this.tickets.filter(t => t.estado === 'estacionado').length;
                    const delivered = this.tickets.filter(t => t.estado === 'entregado').length;
                    response = `📊 <b>Corte Operativo Actual:</b><br>&bull; Total Registros: ${total}<br>&bull; Vehículos en Patio: ${parked}<br>&bull; Entregados: ${delivered}<br>Sistemas sincronizados correctamente.`;
                }
                else if(lower.includes('ayuda')) {
                    response = `💡 <b>Comandos disponibles:</b><br>1. <i>'Registrar auto placas ABC-123'</i><br>2. <i>'Buscar folio 101'</i><br>3. <i>'Corte de caja'</i>`;
                }
                else {
                    response = `Entendido. He procesado tu solicitud en el sistema Club Park. ¿Deseas registrar un nuevo folio o consultar estadísticas?`;
                }

                setTimeout(() => {
                    this.messages.push({ sender: 'ai', text: response });
                    this.save();
                    this.renderChat();
                }, 400);
            }

            handleManualCheckin(e) {
                e.preventDefault();
                const sucursal = document.getElementById('sucursal').value;
                const folio = document.getElementById('folio').value.trim();
                const placas = document.getElementById('placas').value.trim().toUpperCase();
                const vehiculo = document.getElementById('vehiculo').value.trim();

                const nuevo = {
                    id: Date.now().toString(),
                    sucursal,
                    folio,
                    placas,
                    vehiculo,
                    hora: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    estado: 'estacionado'
                };
                this.tickets.unshift(nuevo);
                this.save();
                document.getElementById('checkinForm').reset();
                this.showToast(`Vehículo ${placas} registrado con éxito`);
                this.switchTab('operations');
            }

            setFilter(branch) {
                this.currentFilter = branch;
                document.querySelectorAll('.filter-chip').forEach(c => {
                    if(c.innerText.includes(branch) || (branch==='todos' && c.innerText==='Todos')) {
                        c.className = 'filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white shrink-0 transition';
                    } else {
                        c.className = 'filter-chip px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 shrink-0 transition';
                    }
                });
                this.renderTickets();
            }

            renderTickets() {
                const container = document.getElementById('ticketsContainer');
                const search = document.getElementById('searchInput')?.value.toLowerCase() || '';

                let filtered = this.tickets.filter(t => {
                    const matchB = this.currentFilter === 'todos' || t.sucursal === this.currentFilter;
                    const matchS = t.folio.toLowerCase().includes(search) || t.placas.toLowerCase().includes(search);
                    return matchB && matchS;
                });

                if(filtered.length === 0) {
                    container.innerHTML = `
                        <div class="bg-white rounded-2xl p-8 text-center border border-slate-200/80">
                            <i class="fa-solid fa-car-tunnel text-slate-300 text-3xl mb-2"></i>
                            <p class="text-xs text-slate-500 font-medium">No hay vehículos en esta vista.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = filtered.map(t => `
                    <div onclick="app.openDetail('${t.id}')" class="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm hover:border-brand-500 transition cursor-pointer flex items-center justify-between">
                        <div class="space-y-1">
                            <div class="flex items-center gap-2">
                                <span class="bg-slate-900 text-white text-[10px] font-bold px-2 py-0.5 rounded-md">Folio #${t.folio}</span>
                                <span class="text-xs font-medium text-slate-500"><i class="fa-solid fa-location-dot text-[10px] text-brand-600"></i> ${t.sucursal}</span>
                            </div>
                            <h4 class="font-bold text-slate-800 text-sm">${t.placas} &bull; <span class="font-normal text-slate-500 text-xs">${t.vehiculo}</span></h4>
                            <p class="text-[10px] text-slate-400">Ingreso: ${t.hora}</p>
                        </div>
                        <div>
                            ${t.estado === 'estacionado'
                                ? '<span class="bg-amber-50 text-amber-600 border border-amber-200 text-xs font-semibold px-2.5 py-1 rounded-full">En Patio</span>'
                                : '<span class="bg-emerald-50 text-emerald-600 border border-emerald-200 text-xs font-semibold px-2.5 py-1 rounded-full">Entregado</span>'}
                        </div>
                    </div>
                `).join('');
            }

            openDetail(id) {
                const t = this.tickets.find(i => i.id === id);
                if(!t) return;
                document.getElementById('modalTitle').innerText = `Folio #${t.folio} - ${t.sucursal}`;
                document.getElementById('modalContent').innerHTML = `
                    <div class="bg-slate-50 p-3.5 rounded-xl space-y-1 text-xs">
                        <div class="flex justify-between"><span class="text-slate-400">Placas:</span><span class="font-bold text-slate-800">${t.placas}</span></div>
                        <div class="flex justify-between"><span class="text-slate-400">Vehículo:</span><span class="font-bold text-slate-800">${t.vehiculo}</span></div>
                        <div class="flex justify-between"><span class="text-slate-400">Hora:</span><span class="font-bold text-slate-800">${t.hora}</span></div>
                        <div class="flex justify-between"><span class="text-slate-400">Estatus:</span><span class="font-bold uppercase text-brand-600">${t.estado}</span></div>
                    </div>
                `;
                document.getElementById('modalActions').innerHTML = t.estado === 'estacionado' ? `
                    <button onclick="app.deliver('${t.id}')" class="flex-1 bg-brand-600 text-white font-semibold py-3 rounded-xl text-sm transition">Marcar Entregado</button>
                    <button onclick="app.remove('${t.id}')" class="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm"><i class="fa-solid fa-trash"></i></button>
                ` : `
                    <button onclick="app.closeModal()" class="flex-1 bg-slate-900 text-white font-semibold py-3 rounded-xl text-sm">Cerrar</button>
                    <button onclick="app.remove('${t.id}')" class="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm"><i class="fa-solid fa-trash"></i></button>
                `;
                document.getElementById('detailModal').classList.remove('hidden');
            }

            closeModal() { document.getElementById('detailModal').classList.add('hidden'); }

            deliver(id) {
                const t = this.tickets.find(i => i.id === id);
                if(t) { t.estado = 'entregado'; this.save(); this.closeModal(); this.renderTickets(); this.showToast(`Vehículo ${t.placas} entregado`); }
            }

            remove(id) {
                if(confirm('¿Eliminar registro?')) {
                    this.tickets = this.tickets.filter(i => i.id !== id);
                    this.save(); this.closeModal(); this.renderTickets(); this.showToast('Registro eliminado', 'error');
                }
            }

            syncData() {
                const icon = document.getElementById('syncIcon');
                icon.classList.add('fa-spin');
                setTimeout(() => { icon.classList.remove('fa-spin'); this.showToast('Sincronización Aeroman-AI exitosa'); }, 800);
            }
        }

        const app = new ClubParkAssistantApp();
    </script>
</body>
</html>
