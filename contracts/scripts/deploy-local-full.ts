// Deploys a full local stack:
//   1. MockUSDC (6 decimals)
//   2. PolyVault behind UUPS proxy
//   3. Mints 1,000,000 USDC each to the first 5 Hardhat accounts
//   4. Writes addresses + chain info to contracts/exports/localhost.json
//
// Use:  npx hardhat run scripts/deploy-local-full.ts --network localhost

import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const SIX_DECIMALS = 1_000_000n;
const SEED_AMOUNT = 1_000_000n * SIX_DECIMALS; // 1,000,000 USDC per account
const NUM_FUNDED = 5;

async function main() {
  if (network.name !== "localhost" && network.name !== "hardhat") {
    throw new Error(`This script is only for localhost / hardhat — got ${network.name}`);
  }

  const signers = await ethers.getSigners();
  const [deployer] = signers;
  console.log(`Deployer: ${deployer.address}`);

  // 1. MockUSDC
  const MockUSDC = await ethers.getContractFactory("MockUSDC");
  const usdc = await MockUSDC.deploy();
  await usdc.waitForDeployment();
  const usdcAddress = await usdc.getAddress();
  console.log(`MockUSDC: ${usdcAddress}`);

  // 2. PolyVault (UUPS proxy)
  const PolyVault = await ethers.getContractFactory("PolyVault");
  const vault = await upgrades.deployProxy(
    PolyVault,
    [
      usdcAddress,
      deployer.address, // admin
      deployer.address, // strategist
      deployer.address, // guardian
      deployer.address, // feeRecipient
      24 * 60 * 60,     // withdrawalDelay = 24h
      8000,             // maxAllocation = 80%
      1000,             // performanceFee = 10%
    ],
    { kind: "uups" }
  );
  await vault.waitForDeployment();
  const vaultAddress = await vault.getAddress();
  const implAddress = await upgrades.erc1967.getImplementationAddress(vaultAddress);
  console.log(`PolyVault proxy: ${vaultAddress}`);
  console.log(`PolyVault impl:  ${implAddress}`);

  // 3. Mint USDC to first NUM_FUNDED accounts
  const funded: { address: string; balance: string }[] = [];
  for (let i = 0; i < Math.min(NUM_FUNDED, signers.length); i++) {
    const tx = await usdc.mint(signers[i].address, SEED_AMOUNT);
    await tx.wait();
    funded.push({ address: signers[i].address, balance: SEED_AMOUNT.toString() });
  }
  console.log(`Minted 1,000,000 USDC to ${funded.length} accounts`);

  // 4. Write address book
  const exportsDir = path.resolve(__dirname, "..", "exports");
  if (!fs.existsSync(exportsDir)) fs.mkdirSync(exportsDir, { recursive: true });

  const addressBook = {
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    network: network.name,
    deployedAt: new Date().toISOString(),
    addresses: {
      MockUSDC: usdcAddress,
      PolyVault: vaultAddress,
      PolyVaultImpl: implAddress,
    },
    deployer: deployer.address,
    funded,
  };

  const outPath = path.join(exportsDir, "localhost.json");
  fs.writeFileSync(outPath, JSON.stringify(addressBook, null, 2));
  console.log(`\nAddress book → ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
