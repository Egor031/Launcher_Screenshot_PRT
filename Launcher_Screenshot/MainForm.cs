using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Windows.Forms.VisualStyles;

namespace NxPipelineLauncher
{
    public class MainForm : Form
    {
        // --- UI ---
        private TextBox tbPrt = new TextBox();
        private TextBox tbPng = new TextBox();
        private TextBox tbNxbin = new TextBox();
        private TextBox tbObj = new TextBox();
        private CheckBox cbOverwrite = new CheckBox();
        private Button btnRun = new Button();
        private Button btnBrowsePrt = new Button();
        private Button btnBrowsePng = new Button();
        private Button btnBrowseNxbin = new Button();
        private Button btnBrowseObj = new Button();
        private TextBox tbLog = new TextBox();

        // --- Paths relative to launcher exe folder ---
        private readonly string AppDir;
        private string NxJournalPath => Path.Combine(AppDir, "NX", "export_prt_to_obj_batch.py");
        private string RenderScriptPath => Path.Combine(AppDir, "Render", "render_folder.py");
        private string PortablePythonPath => Path.Combine(AppDir, "Tools", "py311", "python.exe");

        public MainForm()
        {
            AppDir = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);

            Text = "NX Pipeline Launcher (PRT → OBJ → PNG)";
            Width = 980;
            Height = 640;
            StartPosition = FormStartPosition.CenterScreen;

            BuildUi();
            AutoFillNxbinFromUgii();
            Log("Ready.");
        }

        private void BuildUi()
        {
            var pad = 10;

            var layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Fill;
            layout.Padding = new Padding(pad);
            layout.ColumnCount = 3;
            layout.RowCount = 7;

            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 170));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 120));

            // Row heights
            for (int i = 0; i < 5; i++)
                layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

            // --- Row 0: PRT ---
            layout.Controls.Add(new Label() { Text = "PRT folder:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
            tbPrt.Dock = DockStyle.Fill;
            layout.Controls.Add(tbPrt, 1, 0);
            btnBrowsePrt.Text = "Browse…";
            btnBrowsePrt.Dock = DockStyle.Fill;
            btnBrowsePrt.Click += (_, __) => PickFolder(tbPrt, "Select folder with .prt files");
            layout.Controls.Add(btnBrowsePrt, 2, 0);

            // --- Row 1: PNG output ---
            layout.Controls.Add(new Label() { Text = "PNG output folder:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 1);
            tbPng.Dock = DockStyle.Fill;
            tbPng.TextChanged += (_, __) => AutoFillObjIfEmpty();
            layout.Controls.Add(tbPng, 1, 1);
            btnBrowsePng.Text = "Browse…";
            btnBrowsePng.Dock = DockStyle.Fill;
            btnBrowsePng.Click += (_, __) => PickFolder(tbPng, "Select output folder for PNGs");
            layout.Controls.Add(btnBrowsePng, 2, 1);

            // --- Row 2: NXBIN ---
            layout.Controls.Add(new Label() { Text = "NXBIN folder:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 2);
            tbNxbin.Dock = DockStyle.Fill;
            layout.Controls.Add(tbNxbin, 1, 2);
            btnBrowseNxbin.Text = "Browse…";
            btnBrowseNxbin.Dock = DockStyle.Fill;
            btnBrowseNxbin.Click += (_, __) => PickFolder(tbNxbin, "Select NXBIN folder (contains run_journal.exe)");
            layout.Controls.Add(btnBrowseNxbin, 2, 2);

            // --- Row 3: OBJ cache (optional) ---
            layout.Controls.Add(new Label() { Text = "OBJ cache folder (optional):", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 3);
            tbObj.Dock = DockStyle.Fill;
            layout.Controls.Add(tbObj, 1, 3);
            btnBrowseObj.Text = "Browse…";
            btnBrowseObj.Dock = DockStyle.Fill;
            btnBrowseObj.Click += (_, __) => PickFolder(tbObj, "Select folder for OBJ cache");
            layout.Controls.Add(btnBrowseObj, 2, 3);

            // --- Row 4: options ---
            cbOverwrite.Text = "Overwrite PNG";
            cbOverwrite.AutoSize = true;
            cbOverwrite.Anchor = AnchorStyles.Left;
            layout.Controls.Add(new Label() { Text = "Options:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 4);
            layout.Controls.Add(cbOverwrite, 1, 4);

            // --- Row 5: Run button ---
            btnRun.Text = "Запустить";
            btnRun.Dock = DockStyle.Left;
            btnRun.Width = 160;
            btnRun.Click += async (_, __) => await RunPipelineAsync();
            layout.Controls.Add(btnRun, 1, 5);

            // --- Row 6: Log textbox ---
            tbLog.Multiline = true;
            tbLog.ScrollBars = ScrollBars.Vertical;
            tbLog.Dock = DockStyle.Fill;
            tbLog.ReadOnly = true;
            tbLog.Font = new System.Drawing.Font("Consolas", 10);
            layout.Controls.Add(tbLog, 0, 6);
            layout.SetColumnSpan(tbLog, 3);

            Controls.Add(layout);
        }

        private void AutoFillNxbinFromUgii()
        {
            var ugii = Environment.GetEnvironmentVariable("UGII_BASE_DIR") ?? "";
            ugii = ugii.Trim();
            if (string.IsNullOrWhiteSpace(ugii))
                return;

            // Common patterns:
            // UGII_BASE_DIR = D:\Program Files\Siemens\NX1899
            // -> NXBIN = %UGII_BASE_DIR%\NXBIN
            // Sometimes UGII_BASE_DIR ends with \UGII -> NXBIN is one level up
            var candidate1 = Path.Combine(ugii, "NXBIN");
            var candidate2 = Path.Combine(Directory.GetParent(ugii)?.FullName ?? ugii, "NXBIN");

            if (Directory.Exists(candidate1))
                tbNxbin.Text = candidate1;
            else if (Directory.Exists(candidate2))
                tbNxbin.Text = candidate2;
        }

        private void AutoFillObjIfEmpty()
        {
            if (!string.IsNullOrWhiteSpace(tbObj.Text))
                return;

            var png = tbPng.Text.Trim();
            if (Directory.Exists(png))
            {
                tbObj.Text = Path.Combine(png, "_obj_cache");
            }
        }

        private void PickFolder(TextBox target, string title)
        {
            using var dlg = new FolderBrowserDialog();
            dlg.Description = title;
            dlg.UseDescriptionForTitle = true;
            dlg.ShowNewFolderButton = true;

            if (Directory.Exists(target.Text))
                dlg.SelectedPath = target.Text;

            if (dlg.ShowDialog() == DialogResult.OK && !string.IsNullOrWhiteSpace(dlg.SelectedPath))
                target.Text = dlg.SelectedPath;
        }

        private void Log(string line)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(Log), line);
                return;
            }
            var ts = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            tbLog.AppendText($"[{ts}] {line}{Environment.NewLine}");
        }

        private void SetUiEnabled(bool enabled)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<bool>(SetUiEnabled), enabled);
                return;
            }

            btnRun.Enabled = enabled;
            btnBrowsePrt.Enabled = enabled;
            btnBrowsePng.Enabled = enabled;
            btnBrowseNxbin.Enabled = enabled;
            btnBrowseObj.Enabled = enabled;

            tbPrt.ReadOnly = !enabled;
            tbPng.ReadOnly = !enabled;
            tbNxbin.ReadOnly = !enabled;
            tbObj.ReadOnly = !enabled;
            cbOverwrite.Enabled = enabled;
        }

        private bool ValidateInputs(out string prtDir, out string pngDir, out string nxbinDir, out string objDir, out string err)
        {
            prtDir = tbPrt.Text.Trim();
            pngDir = tbPng.Text.Trim();
            nxbinDir = tbNxbin.Text.Trim();
            objDir = tbObj.Text.Trim();
            err = "";

            if (!Directory.Exists(prtDir))
            {
                err = "PRT folder does not exist.";
                return false;
            }
            if (!Directory.Exists(pngDir))
            {
                err = "PNG output folder does not exist.";
                return false;
            }
            if (!Directory.Exists(nxbinDir))
            {
                err = "NXBIN folder does not exist.";
                return false;
            }

            // Verify there is at least one .prt
            var prtCount = Directory.GetFiles(prtDir, "*.prt", SearchOption.TopDirectoryOnly).Length;
            if (prtCount == 0)
            {
                err = "No .prt files found in selected PRT folder (top-level).";
                return false;
            }

            // Create OBJ cache folder if missing
            if (string.IsNullOrWhiteSpace(objDir))
                objDir = Path.Combine(pngDir, "_obj_cache");

            Directory.CreateDirectory(objDir);

            // Validate required project files exist near exe
            if (!File.Exists(NxJournalPath))
            {
                err = $"NX journal not found: {NxJournalPath}";
                return false;
            }
            if (!File.Exists(RenderScriptPath))
            {
                err = $"Render script not found: {RenderScriptPath}";
                return false;
            }
            if (!File.Exists(PortablePythonPath))
            {
                err = $"Portable python not found: {PortablePythonPath}";
                return false;
            }

            // Validate run_journal exists
            var runJournal = Path.Combine(nxbinDir, "run_journal.exe");
            if (!File.Exists(runJournal))
            {
                err = $"run_journal.exe not found in NXBIN: {runJournal}";
                return false;
            }

            // Check write permission to png output
            try
            {
                var testFile = Path.Combine(pngDir, "__write_test.tmp");
                File.WriteAllText(testFile, "test");
                File.Delete(testFile);
            }
            catch (Exception ex)
            {
                err = $"No write access to PNG output folder: {ex.Message}";
                return false;
            }

            return true;
        }

        private async Task RunPipelineAsync()
        {
            if (!ValidateInputs(out var prtDir, out var pngDir, out var nxbinDir, out var objDir, out var err))
            {
                MessageBox.Show(this, err, "Validation error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            SetUiEnabled(false);

            var exportLog = Path.Combine(pngDir, "export_log.txt");
            var renderLog = Path.Combine(pngDir, "render_log.txt");

            Log("=== START ===");
            Log($"PRT: {prtDir}");
            Log($"OBJ: {objDir}");
            Log($"PNG: {pngDir}");
            Log($"NXBIN: {nxbinDir}");
            Log($"Overwrite PNG: {cbOverwrite.Checked}");
            Log($"Export log: {exportLog}");
            Log($"Render log: {renderLog}");

            try
            {
                // Step 1: NX export
                Log("--- Step 1: NX Export PRT -> OBJ ---");
                var runJournalExe = Path.Combine(nxbinDir, "run_journal.exe");

                var env = new ProcessStartInfo().Environment; // empty template not used
                // We'll pass env via ProcessStartInfo.EnvironmentVariables below.

                var rc1 = await RunProcessAsync(
                    fileName: runJournalExe,
                    arguments: $"\"{NxJournalPath}\"",
                    workingDir: nxbinDir,
                    extraEnv: new (string key, string value)[]
                    {
                        ("PRT_DIR", prtDir),
                        ("OBJ_DIR", objDir),
                        ("LOG_FILE", exportLog)
                    }
                );

                if (rc1 != 0)
                {
                    Log($"NX export failed. Exit code: {rc1}");
                    MessageBox.Show(this, $"NX export failed. See:\n{exportLog}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                // Step 2: Render
                Log("--- Step 2: Render OBJ -> PNG ---");

                var overwriteArg = cbOverwrite.Checked ? " --overwrite" : "";
                //var edgesArg = " --edges";   // <-- добавили
                var views = "Front,Back,Right,Left,Top,Bottom,Isometric,Trimetric";

                var rc2 = await RunProcessAsync(
                    fileName: PortablePythonPath,
                    arguments: $"\"{RenderScriptPath}\" --input \"{objDir}\" --output \"{pngDir}\" --views \"{views}\" --log \"{renderLog}\"{overwriteArg}",
                    workingDir: AppDir,
                    extraEnv: Array.Empty<(string key, string value)>()
                );


                if (rc2 != 0)
                {
                    Log($"Render failed. Exit code: {rc2}");
                    MessageBox.Show(this, $"Render failed. See:\n{renderLog}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                Log("=== DONE ===");
                MessageBox.Show(this, "Done!", "OK", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            finally
            {
                SetUiEnabled(true);
            }
        }

        private Task<int> RunProcessAsync(string fileName, string arguments, string workingDir, (string key, string value)[] extraEnv)
        {
            return Task.Run(() =>
            {
                var psi = new ProcessStartInfo
                {
                    FileName = fileName,
                    Arguments = arguments,
                    WorkingDirectory = workingDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8,
                };

                // inherit current env + add/override
                foreach (System.Collections.DictionaryEntry de in Environment.GetEnvironmentVariables())
                {
                    var k = (string)de.Key;
                    var v = (string)de.Value;
                    psi.EnvironmentVariables[k] = v;
                }
                foreach (var (key, value) in extraEnv)
                {
                    psi.EnvironmentVariables[key] = value;
                }

                Log($"CMD: {psi.FileName} {psi.Arguments}");

                using var p = new Process();
                p.StartInfo = psi;

                p.OutputDataReceived += (_, e) => { if (e.Data != null) Log(e.Data); };
                p.ErrorDataReceived += (_, e) => { if (e.Data != null) Log("[ERR] " + e.Data); };

                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                p.WaitForExit();
                return p.ExitCode;
            });
        }
    }
}
