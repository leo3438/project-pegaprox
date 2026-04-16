        // ═══════════════════════════════════════════════
        // PegaProx - Authentication
        // LoginScreen component
        // ═══════════════════════════════════════════════
        
        // Login Screen Component
        // LW: Keep this simple - first thing users see!
        function LoginScreen() {
            const { t } = useTranslation();
            const { login, error, ldapEnabled, oidcEnabled, oidcButtonText, loginBackground } = useAuth();
            const [username, setUsername] = useState('');
            const [password, setPassword] = useState('');
            const [totpCode, setTotpCode] = useState('');
            const [loading, setLoading] = useState(false);
            const [showPassword, setShowPassword] = useState(false);
            const [requires2FA, setRequires2FA] = useState(false);
            const [rememberMe, setRememberMe] = useState(() => localStorage.getItem('pegaprox-remember') === 'true');
            
            const [oidcLoading, setOidcLoading] = useState(false);
            
            // NS: Feb 2026 - Handle OIDC callback (check URL for auth code on mount)
            React.useEffect(() => {
                const params = new URLSearchParams(window.location.search);
                const code = params.get('code');
                const state = params.get('state');
                if (code && state) {
                    // We got redirected back from IdP with auth code
                    setOidcLoading(true);
                    fetch(`${API_URL}/auth/oidc/callback`, {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code, state })
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            // NS: Apr 2026 - redirect to portal if OIDC flow was started from there
                            if (data.redirect_after && data.redirect_after.startsWith('/')) {
                                window.location.href = data.redirect_after;
                                return;
                            }
                            // Clear URL params and reload to authenticated state
                            window.history.replaceState({}, '', window.location.pathname);
                            window.location.reload();
                        } else {
                            setOidcError(data.error || 'OIDC authentication failed');
                            window.history.replaceState({}, '', window.location.pathname);
                        }
                    })
                    .catch(() => { setOidcError('Network error during OIDC callback'); })
                    .finally(() => setOidcLoading(false));
                }
            }, []);
            
            const [oidcError, setOidcError] = useState('');
            
            const handleOidcLogin = async () => {
                setOidcLoading(true);
                setOidcError('');
                try {
                    const res = await fetch(`${API_URL}/auth/oidc/authorize`, { credentials: 'include' });
                    const data = await res.json();
                    if (data.auth_url && data.auth_url.startsWith('https://')) {
                        window.location.href = data.auth_url;
                    } else if (data.auth_url) {
                        // NS: Mar 2026 - block non-https redirects (open redirect prevention)
                        console.error('OIDC auth_url must use https');
                        setOidcError('Insecure authentication URL rejected');
                    } else {
                        setOidcError(data.error || 'Failed to get authorization URL');
                        setOidcLoading(false);
                    }
                } catch (e) {
                    setOidcError('Network error');
                    setOidcLoading(false);
                }
            };
            
            const handleSubmit = async (e) => {
                e.preventDefault();
                if (!username || !password) return;
                if (requires2FA && !totpCode) return;
                
                setLoading(true);
                localStorage.setItem('pegaprox-remember', rememberMe);
                const result = await login(username, password, totpCode, rememberMe);
                
                if (result?.requires_2fa) {
                    setRequires2FA(true);
                }
                setLoading(false);
            };
            
            return(
                <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
                    style={loginBackground ? {
                        backgroundImage: `url(${loginBackground})`,
                        backgroundSize: 'cover',
                        backgroundPosition: 'center',
                        backgroundRepeat: 'no-repeat'
                    } : { background: 'linear-gradient(135deg, #060810 0%, #0b0f1a 50%, #080B0E 100%)' }}>

                    {/* Animated background orbs */}
                    {!loginBackground && (<>
                        <style>{`
                            @keyframes float1 { 0%,100%{transform:translate(0,0) scale(1)} 33%{transform:translate(40px,-30px) scale(1.05)} 66%{transform:translate(-20px,20px) scale(0.97)} }
                            @keyframes float2 { 0%,100%{transform:translate(0,0) scale(1)} 33%{transform:translate(-50px,25px) scale(1.08)} 66%{transform:translate(30px,-15px) scale(0.95)} }
                            @keyframes float3 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(20px,40px) scale(1.04)} }
                            @keyframes fadeSlideUp { from{opacity:0;transform:translateY(24px)} to{opacity:1;transform:translateY(0)} }
                            .login-card-animate { animation: fadeSlideUp 0.5s cubic-bezier(.22,1,.36,1) both; }
                            .login-input:focus { box-shadow: 0 0 0 2px rgba(229,112,0,0.35); border-color: #E57000 !important; }
                            .login-btn { background: linear-gradient(135deg, #E57000 0%, #c85e00 100%); transition: all 0.2s ease; }
                            .login-btn:hover:not(:disabled) { background: linear-gradient(135deg, #ff8c00 0%, #E57000 100%); transform: translateY(-1px); box-shadow: 0 8px 25px rgba(229,112,0,0.35); }
                            .login-btn:active:not(:disabled) { transform: translateY(0); }
                        `}</style>
                        <div style={{position:'absolute',top:'-15%',left:'-10%',width:'55vw',height:'55vw',maxWidth:700,maxHeight:700,borderRadius:'50%',background:'radial-gradient(circle, rgba(229,112,0,0.12) 0%, transparent 70%)',animation:'float1 18s ease-in-out infinite',pointerEvents:'none'}} />
                        <div style={{position:'absolute',bottom:'-20%',right:'-10%',width:'60vw',height:'60vw',maxWidth:750,maxHeight:750,borderRadius:'50%',background:'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)',animation:'float2 22s ease-in-out infinite',pointerEvents:'none'}} />
                        <div style={{position:'absolute',top:'40%',right:'20%',width:'30vw',height:'30vw',maxWidth:400,maxHeight:400,borderRadius:'50%',background:'radial-gradient(circle, rgba(229,112,0,0.06) 0%, transparent 70%)',animation:'float3 14s ease-in-out infinite',pointerEvents:'none'}} />
                    </>)}

                    {loginBackground && <div className="absolute inset-0 bg-black/50" />}

                    <div className="w-full max-w-md relative z-10 login-card-animate">

                        {/* Logo and Title */}
                        <div className="text-center mb-8">
                            <div className="relative inline-block mb-5">
                                <div style={{position:'absolute',inset:'-6px',borderRadius:'50%',background:'conic-gradient(from 0deg, #E57000, #ff8c00, #E57000)',opacity:0.5,filter:'blur(6px)'}} />
                                <img
                                    src="/images/pegaprox.png"
                                    alt="PegaProx"
                                    className="relative w-24 h-24 rounded-full object-cover"
                                    style={{boxShadow:'0 0 0 2px rgba(229,112,0,0.4)'}}
                                    onError={(e) => {
                                        e.target.outerHTML = '<div style="position:relative;width:96px;height:96px;border-radius:50%;background:linear-gradient(135deg,#E57000,#c85e00);display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 2px rgba(229,112,0,0.4)"><svg width="48" height="48" fill="none" stroke="white" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/></svg></div>';
                                    }}
                                />
                            </div>
                            <h1 className="text-4xl font-bold text-white mb-1" style={{letterSpacing:'-0.5px'}}>PegaProx</h1>
                            <p className="text-sm" style={{color:'rgba(255,255,255,0.4)'}}>{t('loginSubtitle')}</p>
                        </div>

                        {/* Glassmorphism Card */}
                        <div style={{
                            background: 'rgba(255,255,255,0.04)',
                            backdropFilter: 'blur(24px)',
                            WebkitBackdropFilter: 'blur(24px)',
                            border: '1px solid rgba(255,255,255,0.08)',
                            borderRadius: '20px',
                            padding: '2rem',
                            boxShadow: '0 25px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)'
                        }}>
                            <h2 className="text-lg font-semibold text-white mb-6" style={{letterSpacing:'-0.2px'}}>
                                {requires2FA ? t('twoFARequired') : t('loginTitle')}
                            </h2>

                            {error && (
                                <div className="mb-4 p-3 rounded-xl text-sm flex items-center gap-2" style={{background:'rgba(239,68,68,0.1)',border:'1px solid rgba(239,68,68,0.25)',color:'#f87171'}}>
                                    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    {error}
                                </div>
                            )}

                            <form onSubmit={handleSubmit} className="space-y-4">
                                {!requires2FA ? (<>
                                    <div>
                                        <label className="block text-xs font-medium mb-1.5" style={{color:'rgba(255,255,255,0.5)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
                                            {t('usernameLabel')}
                                        </label>
                                        <input
                                            type="text"
                                            value={username}
                                            onChange={(e) => setUsername(e.target.value)}
                                            className="login-input w-full px-4 py-3 rounded-xl text-white placeholder-gray-600 focus:outline-none transition-all"
                                            style={{background:'rgba(0,0,0,0.35)',border:'1px solid rgba(255,255,255,0.08)',fontSize:'0.95rem'}}
                                            placeholder="pegaprox"
                                            autoComplete="username"
                                            autoFocus
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium mb-1.5" style={{color:'rgba(255,255,255,0.5)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
                                            {t('passwordLabel')}
                                        </label>
                                        <div className="relative">
                                            <input
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                className="login-input w-full px-4 py-3 pr-12 rounded-xl text-white placeholder-gray-600 focus:outline-none transition-all"
                                                style={{background:'rgba(0,0,0,0.35)',border:'1px solid rgba(255,255,255,0.08)',fontSize:'0.95rem'}}
                                                placeholder="••••••••"
                                                autoComplete="current-password"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                                                style={{color:'rgba(255,255,255,0.3)'}}
                                                onMouseEnter={e=>e.currentTarget.style.color='rgba(255,255,255,0.7)'}
                                                onMouseLeave={e=>e.currentTarget.style.color='rgba(255,255,255,0.3)'}
                                            >
                                                {showPassword ? (
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                                                ) : (
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </>) : (
                                    <div>
                                        <label className="block text-xs font-medium mb-1.5" style={{color:'rgba(255,255,255,0.5)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
                                            {t('enter2FACode')}
                                        </label>
                                        <input
                                            type="text"
                                            value={totpCode}
                                            onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                            className="login-input w-full px-4 py-3 rounded-xl text-white text-center text-2xl tracking-widest placeholder-gray-600 focus:outline-none transition-all"
                                            style={{background:'rgba(0,0,0,0.35)',border:'1px solid rgba(255,255,255,0.08)'}}
                                            placeholder="000000"
                                            maxLength={6}
                                            autoFocus
                                        />
                                        <p className="text-xs mt-2 text-center" style={{color:'rgba(255,255,255,0.4)'}}>{t('scan2FACode')}</p>
                                    </div>
                                )}

                                <label className="flex items-center gap-2 text-sm cursor-pointer select-none" style={{color:'rgba(255,255,255,0.4)'}}>
                                    <input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)}
                                        className="rounded"
                                        style={{accentColor:'#E57000'}} />
                                    {t('rememberMe') || 'Remember me'}
                                </label>

                                <button
                                    type="submit"
                                    disabled={loading || !username || !password}
                                    className="login-btn w-full py-3 rounded-xl text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none"
                                    style={{fontSize:'0.95rem',letterSpacing:'0.01em'}}
                                >
                                    {loading ? (<>
                                        <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        {t('loggingIn')}
                                    </>) : t('loginButton')}
                                </button>
                            </form>

                            {/* NS: Feb 2026 - OIDC / Entra ID login */}
                            {oidcEnabled && (
                                <div className="mt-4">
                                    <div className="flex items-center gap-3 mb-4">
                                        <div className="flex-1 h-px" style={{background:'rgba(255,255,255,0.08)'}}></div>
                                        <span className="text-xs" style={{color:'rgba(255,255,255,0.25)',textTransform:'uppercase',letterSpacing:'0.08em'}}>or</span>
                                        <div className="flex-1 h-px" style={{background:'rgba(255,255,255,0.08)'}}></div>
                                    </div>
                                    <button onClick={handleOidcLogin} disabled={oidcLoading}
                                        className={`w-full flex items-center justify-center gap-3 px-4 py-2.5 disabled:opacity-50 rounded-xl text-white font-medium text-sm transition-colors ${
                                            (oidcButtonText || '').toLowerCase().includes('microsoft') || (oidcButtonText || '').toLowerCase().includes('entra')
                                                ? 'bg-[#0078d4] hover:bg-[#106ebe]'
                                                : (oidcButtonText || '').toLowerCase().includes('google')
                                                    ? 'bg-white hover:bg-gray-100 text-gray-700 border border-gray-300'
                                                    : ''
                                        }`}
                                        style={(oidcButtonText || '').toLowerCase().includes('microsoft') || (oidcButtonText || '').toLowerCase().includes('google') ? {} : {background:'rgba(255,255,255,0.06)',border:'1px solid rgba(255,255,255,0.1)'}}>
                                        {oidcLoading ? (
                                            <Icons.Loader className="w-5 h-5 animate-spin" />
                                        ) : (oidcButtonText || '').toLowerCase().includes('microsoft') || (oidcButtonText || '').toLowerCase().includes('entra') ? (
                                            <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none"><path d="M0 0h10v10H0z" fill="#f25022"/><path d="M11 0h10v10H11z" fill="#7fba00"/><path d="M0 11h10v10H0z" fill="#00a4ef"/><path d="M11 11h10v10H11z" fill="#ffb900"/></svg>
                                        ) : (
                                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
                                        )}
                                        {oidcButtonText || 'Sign in with SSO'}
                                    </button>
                                    {oidcError && <p className="text-red-400 text-xs text-center mt-2">{oidcError}</p>}
                                </div>
                            )}

                            {/* MK: Feb 2026 - LDAP indicator */}
                            {ldapEnabled && (
                                <div className="mt-3 flex items-center justify-center gap-2 text-xs" style={{color:'rgba(255,255,255,0.3)'}}>
                                    <Icons.Users className="w-3 h-3" />
                                    <span>LDAP / Active Directory enabled</span>
                                </div>
                            )}
                        </div>

                        {/* Language Switcher */}
                        <div className="flex justify-center mt-5">
                            <LanguageSwitcher />
                        </div>

                        {/* Footer */}
                        <p className="text-center text-xs mt-4" style={{color:'rgba(255,255,255,0.2)'}}>
                            PegaProx Cluster Management {PEGAPROX_VERSION}
                        </p>
                    </div>
                </div>
            );
        }

