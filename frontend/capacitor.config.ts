import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ro.asistentmedical.ai",
  appName: "Asistent Medical AI",
  webDir: "out",
  server: {
    androidScheme: "https"
  }
};

export default config;
