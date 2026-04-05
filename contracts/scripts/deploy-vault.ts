import { ethers, upgrades } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // Configuration - adjust these for your deployment
  const USDC_ADDRESS = process.env.USDC_ADDRESS || "";
  const ADMIN_ADDRESS = deployer.address;
  const STRATEGIST_ADDRESS = process.env.STRATEGIST_ADDRESS || deployer.address;
  const GUARDIAN_ADDRESS = process.env.GUARDIAN_ADDRESS || deployer.address;
  const FEE_RECIPIENT = process.env.FEE_RECIPIENT || deployer.address;

  const WITHDRAWAL_DELAY = 24 * 60 * 60; // 24 hours
  const MAX_ALLOCATION = 8000; // 80% in basis points
  const PERFORMANCE_FEE = 1000; // 10% in basis points

  if (!USDC_ADDRESS) {
    console.error("ERROR: Set USDC_ADDRESS in env or .env file");
    process.exit(1);
  }

  console.log("Deploying PolyVault proxy + implementation...");

  const PolyVault = await ethers.getContractFactory("PolyVault");
  const vault = await upgrades.deployProxy(
    PolyVault,
    [
      USDC_ADDRESS,
      ADMIN_ADDRESS,
      STRATEGIST_ADDRESS,
      GUARDIAN_ADDRESS,
      FEE_RECIPIENT,
      WITHDRAWAL_DELAY,
      MAX_ALLOCATION,
      PERFORMANCE_FEE,
    ],
    { kind: "uups" }
  );

  await vault.waitForDeployment();
  const proxyAddress = await vault.getAddress();
  const implAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);

  console.log("PolyVault proxy deployed to:", proxyAddress);
  console.log("Implementation deployed to:", implAddress);
  console.log("");
  console.log("Configuration:");
  console.log("  USDC:", USDC_ADDRESS);
  console.log("  Admin:", ADMIN_ADDRESS);
  console.log("  Strategist:", STRATEGIST_ADDRESS);
  console.log("  Guardian:", GUARDIAN_ADDRESS);
  console.log("  Fee Recipient:", FEE_RECIPIENT);
  console.log("  Withdrawal Delay:", WITHDRAWAL_DELAY, "seconds");
  console.log("  Max Allocation:", MAX_ALLOCATION, "bps");
  console.log("  Performance Fee:", PERFORMANCE_FEE, "bps");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
