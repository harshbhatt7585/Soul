import { loadConfig } from "./config.js";
import { WhatsAppGateway } from "./whatsapp-gateway.js";

async function main() {
  const config = loadConfig();
  const gateway = new WhatsAppGateway(config);
  await gateway.start();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
