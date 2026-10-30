import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const env = { ...loadEnv(mode, root, ''), ...process.env }
  const unsafe = Object.keys(env).filter(key => /^(VITE_|NEXT_PUBLIC_).*(SECRET|SERVICE_ROLE|GEMINI|GOOGLE_API|TOKEN|PASSWORD)/i.test(key) && env[key])
  if (unsafe.length) throw new Error(`Move these secrets to server-only variable names: ${unsafe.join(', ')}`)
  const first = (...names: string[]) => names.map(name => env[name]?.trim()).find(Boolean) || ''
  return {
    plugins: [react(), tailwindcss()],
    // Do not expose process.env or change envPrefix to include NEXT_PUBLIC_.
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(first('VITE_API_BASE_URL')),
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(first('SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_URL', 'VITE_SUPABASE_URL')),
      'import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY': JSON.stringify(first('SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_ANON_KEY', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_SUPABASE_ANON_KEY')),
    },
    server: { proxy: { '/health': 'http://127.0.0.1:8000' } },
  }
})
