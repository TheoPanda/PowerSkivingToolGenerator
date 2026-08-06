/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'
import renderer from 'vite-plugin-electron-renderer'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const isElectron = mode === 'electron'

  const plugins: any[] = [vue()]

  if (isElectron) {
    plugins.push(
      electron([
        {
          entry: 'electron/main.ts',
          vite: {
            build: {
              outDir: 'dist-electron',
              rollupOptions: {
                external: ['electron'],
              },
            },
          },
        },
        {
          entry: 'electron/preload.ts',
          onstart(args) {
            args.reload()
          },
          vite: {
            build: {
              outDir: 'dist-electron',
              rollupOptions: {
                external: ['electron'],
              },
            },
          },
        },
      ]),
      renderer(),
    )
  }

  return {
    plugins,
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '/logo.png': resolve(__dirname, 'public/logo.png'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:5199',
          changeOrigin: true,
        },
      },
    },
    test: {
      root: __dirname,
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{ts,js}'],
      setupFiles: ['./src/test-setup.ts'],
      server: {
        deps: {
          inline: ['element-plus'],
        },
      },
      css: true,
      env: {
        VITE_BACKEND_URL: 'http://127.0.0.1:5199',
      },
      deps: {
        optimizer: {
          web: {
            include: ['vue', '@vue/test-utils'],
          },
        },
      },
    },
  }
})
