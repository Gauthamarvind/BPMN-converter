import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { spawn } from 'child_process';
import { defineConfig, Plugin } from 'vite';

function process2bpmnApiPlugin(): Plugin {
  return {
    name: 'process2bpmn-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url || !req.url.startsWith('/api/')) {
          return next();
        }

        const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
        const pathname = url.pathname;

        let cmd = '';
        const tplMatch = pathname.match(/^\/api\/templates\/([^\/]+)(?:\/default)?$/);

        if (pathname === '/api/health') {
          cmd = 'health';
        } else if (pathname === '/api/profiles') {
          cmd = 'profiles';
        } else if (pathname === '/api/samples') {
          cmd = 'samples';
        } else if (pathname === '/api/convert' || pathname === '/api/convert-json') {
          cmd = 'convert';
        } else if (pathname === '/api/lint') {
          cmd = 'lint';
        } else if (pathname === '/api/templates' || pathname === '/api/templates/') {
          cmd = req.method === 'POST' ? 'templates_save' : 'templates_list';
        } else if (pathname === '/api/templates/map-lanes') {
          cmd = 'templates_map_lanes';
        } else if (pathname === '/api/templates/download-blank') {
          cmd = 'templates_blank';
        } else if (tplMatch) {
          const tplId = tplMatch[1];
          if (pathname.endsWith('/default')) {
            cmd = 'templates_default';
          } else if (req.method === 'DELETE') {
            cmd = 'templates_delete';
          } else {
            cmd = 'templates_get';
          }
        } else {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: `Not found: ${pathname}` }));
          return;
        }

        // Collect request body
        const chunks: Buffer[] = [];
        req.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
        req.on('end', () => {
          const bodyBuffer = Buffer.concat(chunks);
          let stdinData = '';

          const contentType = req.headers['content-type'] || '';
          if (contentType.includes('application/json')) {
            stdinData = bodyBuffer.toString('utf-8');
          } else if (contentType.includes('multipart/form-data') || req.method === 'POST') {
            const raw = bodyBuffer.toString('utf-8');
            if (raw.includes('name="text"') || raw.includes('name="file"') || raw.includes('name="template_id"')) {
              let text = '';
              let profile = 'generic';
              let filename = 'uploaded_process.txt';
              let template_id = '';
              let lane_map = '';

              const textMatch = raw.match(/name="text"[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (textMatch) text = textMatch[1].trim();

              const profMatch = raw.match(/name="profile"[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (profMatch) profile = profMatch[1].trim();

              const tplMatchField = raw.match(/name="template_id"[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (tplMatchField) template_id = tplMatchField[1].trim();

              const laneMatchField = raw.match(/name="lane_map"[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (laneMatchField) lane_map = laneMatchField[1].trim();

              const fnameMatch = raw.match(/filename="([^"]+)"[\r\n]+Content-Type:[^\r\n]+[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (fnameMatch) {
                filename = fnameMatch[1];
                if (!text) text = fnameMatch[2].trim();
              }

              // Also support xml file upload for templates_save
              let xml = '';
              const xmlMatch = raw.match(/filename="([^"]+\.(?:bpmn|xml))"[\r\n]+Content-Type:[^\r\n]+[\r\n]+([\s\S]*?)[\r\n]+------/);
              if (xmlMatch) {
                xml = xmlMatch[2].trim();
              }

              let parsedLaneMap = undefined;
              if (lane_map) {
                try { parsedLaneMap = JSON.parse(lane_map); } catch (_) {}
              }

              stdinData = JSON.stringify({
                text,
                xml,
                name: filename.replace(/\.(bpmn|xml)$/, '').replace(/_/g, ' '),
                filename,
                profile,
                template_id: template_id || undefined,
                lane_map: parsedLaneMap,
                mock: false
              });
            } else {
              stdinData = JSON.stringify({ text: raw, profile: 'generic', filename: 'input.txt', mock: false });
            }
          }

          // If query params exist (e.g. for download-blank or templates_get)
          if (cmd === 'templates_blank') {
            const fmt = url.searchParams.get('type') || 'xlsx';
            const sample = url.searchParams.get('sample') !== 'false';
            stdinData = JSON.stringify({ type: fmt, sample });
          } else if (tplMatch && !stdinData) {
            stdinData = JSON.stringify({ template_id: tplMatch[1] });
          }

          const pyArgs = [path.resolve(process.cwd(), 'backend/bridge.py'), cmd];
          if (tplMatch) {
            pyArgs.push(tplMatch[1]);
          }

          const py = spawn('python3', pyArgs, {
            cwd: process.cwd(),
          });

          let stdout = '';
          let stderr = '';

          if (stdinData) {
            py.stdin.write(stdinData);
          }
          py.stdin.end();

          py.stdout.on('data', (data) => {
            stdout += data.toString();
          });

          py.stderr.on('data', (data) => {
            stderr += data.toString();
          });

          py.on('close', (code) => {
            let output = stdout.trim();
            const firstBrace = output.indexOf('{');
            const lastBrace = output.lastIndexOf('}');
            if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
              output = output.substring(firstBrace, lastBrace + 1);
            }

            if (code !== 0 && !output) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: stderr || `Process failed with exit code ${code}` }));
              return;
            }

            // Handle blank template file download streaming
            if (cmd === 'templates_blank') {
              try {
                const parsed = JSON.parse(output);
                if (parsed.base64 && parsed.filename) {
                  const bin = Buffer.from(parsed.base64, 'base64');
                  res.writeHead(200, {
                    'Content-Type': parsed.media_type,
                    'Content-Disposition': `attachment; filename="${parsed.filename}"`,
                    'Content-Length': bin.length
                  });
                  res.end(bin);
                  return;
                }
              } catch (_) {}
            }

            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(output);
          });
        });
      });
    },
  };
}

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss(), process2bpmnApiPlugin()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
