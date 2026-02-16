using Launcher_Screenshot;
using System;
using System.Windows.Forms;

namespace NxPipelineLauncher
{
    internal static class Program
    {
        [STAThread]
        static void Main()
        {
            ApplicationConfiguration.Initialize();
            Application.Run(new MainForm());
        }
    }
}
