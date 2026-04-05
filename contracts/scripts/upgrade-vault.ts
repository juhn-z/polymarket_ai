import { ethers, upgrades } from "hardhat";

async function main() {
  const PROXY_ADDRESS = process.env.VAULT_PROXY_ADDRESS || "";

  if (!PROXY_ADDRESS) {
    console.error("ERROR: Set VAULT_PROXY_ADDRESS in env");
    process.exit(1);
  }

  console.log("Upgrading PolyVault at:", PROXY_ADDRESS);

  const PolyVaultV2 = await ethers.getContractFactory("PolyVault");
  const upgraded = await upgrades.upgradeProxy(PROXY_ADDRESS, PolyVaultV2, {
    kind: "uups",
  });

  await upgraded.waitForDeployment();
  const newImpl = await upgrades.erc1967.getImplementationAddress(PROXY_ADDRESS);

  console.log("PolyVault upgraded successfully");
  console.log("New implementation:", newImpl);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
