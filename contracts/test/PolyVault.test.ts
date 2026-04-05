import { expect } from "chai";
import { ethers, upgrades } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { PolyVault, MockUSDC } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("PolyVault", function () {
  const WITHDRAWAL_DELAY = 24 * 60 * 60; // 24 hours
  const MAX_ALLOCATION = 8000; // 80%
  const PERFORMANCE_FEE = 1000; // 10%
  const BASIS_POINTS = 10_000;
  const USDC_DECIMALS = 6;

  function usdc(amount: number): bigint {
    return ethers.parseUnits(amount.toString(), USDC_DECIMALS);
  }

  async function deployFixture() {
    const [admin, strategist, guardian, feeRecipient, user1, user2] =
      await ethers.getSigners();

    const MockUSDC = await ethers.getContractFactory("MockUSDC");
    const usdcToken = await MockUSDC.deploy();

    const PolyVault = await ethers.getContractFactory("PolyVault");
    const vault = (await upgrades.deployProxy(
      PolyVault,
      [
        await usdcToken.getAddress(),
        admin.address,
        strategist.address,
        guardian.address,
        feeRecipient.address,
        WITHDRAWAL_DELAY,
        MAX_ALLOCATION,
        PERFORMANCE_FEE,
      ],
      { kind: "uups" }
    )) as unknown as PolyVault;

    // Mint USDC to test users
    await usdcToken.mint(user1.address, usdc(100_000));
    await usdcToken.mint(user2.address, usdc(100_000));
    await usdcToken.mint(strategist.address, usdc(100_000));

    // Approve vault for users
    await usdcToken.connect(user1).approve(await vault.getAddress(), ethers.MaxUint256);
    await usdcToken.connect(user2).approve(await vault.getAddress(), ethers.MaxUint256);
    await usdcToken
      .connect(strategist)
      .approve(await vault.getAddress(), ethers.MaxUint256);

    return { vault, usdcToken, admin, strategist, guardian, feeRecipient, user1, user2 };
  }

  // ==================== INITIALIZATION ====================

  describe("Initialization", function () {
    it("should set correct token name and symbol", async function () {
      const { vault } = await loadFixture(deployFixture);
      expect(await vault.name()).to.equal("PolyVault USDC");
      expect(await vault.symbol()).to.equal("pvUSDC");
    });

    it("should set correct parameters", async function () {
      const { vault, usdcToken } = await loadFixture(deployFixture);
      expect(await vault.asset()).to.equal(await usdcToken.getAddress());
      expect(await vault.withdrawalDelay()).to.equal(WITHDRAWAL_DELAY);
      expect(await vault.maxStrategyAllocation()).to.equal(MAX_ALLOCATION);
      expect(await vault.performanceFee()).to.equal(PERFORMANCE_FEE);
      expect(await vault.minDeposit()).to.equal(usdc(1));
      expect(await vault.maxDeposit()).to.equal(usdc(100_000));
    });

    it("should assign roles correctly", async function () {
      const { vault, admin, strategist, guardian } = await loadFixture(deployFixture);
      const ADMIN_ROLE = await vault.DEFAULT_ADMIN_ROLE();
      const STRATEGIST_ROLE = await vault.STRATEGIST_ROLE();
      const GUARDIAN_ROLE = await vault.GUARDIAN_ROLE();

      expect(await vault.hasRole(ADMIN_ROLE, admin.address)).to.be.true;
      expect(await vault.hasRole(STRATEGIST_ROLE, strategist.address)).to.be.true;
      expect(await vault.hasRole(GUARDIAN_ROLE, guardian.address)).to.be.true;
    });

    it("should revert on zero address", async function () {
      const [admin] = await ethers.getSigners();
      const MockUSDC = await ethers.getContractFactory("MockUSDC");
      const usdcToken = await MockUSDC.deploy();
      const PolyVault = await ethers.getContractFactory("PolyVault");

      await expect(
        upgrades.deployProxy(
          PolyVault,
          [
            ethers.ZeroAddress,
            admin.address,
            admin.address,
            admin.address,
            admin.address,
            WITHDRAWAL_DELAY,
            MAX_ALLOCATION,
            PERFORMANCE_FEE,
          ],
          { kind: "uups" }
        )
      ).to.be.revertedWithCustomError(PolyVault, "ZeroAddress");
    });

    it("should revert on invalid withdrawal delay", async function () {
      const [admin] = await ethers.getSigners();
      const MockUSDC = await ethers.getContractFactory("MockUSDC");
      const usdcToken = await MockUSDC.deploy();
      const PolyVault = await ethers.getContractFactory("PolyVault");

      await expect(
        upgrades.deployProxy(
          PolyVault,
          [
            await usdcToken.getAddress(),
            admin.address,
            admin.address,
            admin.address,
            admin.address,
            60, // 1 minute - too short
            MAX_ALLOCATION,
            PERFORMANCE_FEE,
          ],
          { kind: "uups" }
        )
      ).to.be.revertedWithCustomError(PolyVault, "InvalidWithdrawalDelay");
    });
  });

  // ==================== DEPOSITS ====================

  describe("Deposits", function () {
    it("should accept deposit and mint shares", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);

      expect(await vault.balanceOf(user1.address)).to.be.gt(0);
      expect(await vault.totalAssets()).to.equal(usdc(1000));
    });

    it("should reject deposit below minimum", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).deposit(usdc(0.5), user1.address)
      ).to.be.revertedWithCustomError(vault, "DepositBelowMinimum");
    });

    it("should reject deposit above maximum", async function () {
      const { vault, usdcToken, user1 } = await loadFixture(deployFixture);

      await usdcToken.mint(user1.address, usdc(200_000));
      await expect(
        vault.connect(user1).deposit(usdc(150_000), user1.address)
      ).to.be.revertedWithCustomError(vault, "DepositAboveMaximum");
    });

    it("should reject deposit when paused", async function () {
      const { vault, guardian, user1 } = await loadFixture(deployFixture);

      await vault.connect(guardian).pause();
      await expect(
        vault.connect(user1).deposit(usdc(1000), user1.address)
      ).to.be.revertedWithCustomError(vault, "EnforcedPause");
    });

    it("should allow multiple users to deposit", async function () {
      const { vault, user1, user2 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      await vault.connect(user2).deposit(usdc(2000), user2.address);

      expect(await vault.totalAssets()).to.equal(usdc(3000));
    });
  });

  // ==================== DELAYED WITHDRAWAL ====================

  describe("Delayed Withdrawal", function () {
    it("should request, wait, and execute withdrawal", async function () {
      const { vault, usdcToken, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);

      // Request withdrawal
      await vault.connect(user1).requestWithdraw(shares);
      expect(await vault.balanceOf(user1.address)).to.equal(0);

      const req = await vault.getWithdrawalRequest(user1.address);
      expect(req.pending).to.be.true;
      expect(req.shares).to.equal(shares);

      // Cannot execute before delay
      await expect(
        vault.connect(user1).executeWithdraw()
      ).to.be.revertedWithCustomError(vault, "WithdrawalDelayNotMet");

      // Wait for delay
      await time.increase(WITHDRAWAL_DELAY);

      // Execute withdrawal
      const balanceBefore = await usdcToken.balanceOf(user1.address);
      await vault.connect(user1).executeWithdraw();
      const balanceAfter = await usdcToken.balanceOf(user1.address);

      expect(balanceAfter - balanceBefore).to.equal(usdc(1000));
      expect(await vault.balanceOf(user1.address)).to.equal(0);

      const reqAfter = await vault.getWithdrawalRequest(user1.address);
      expect(reqAfter.pending).to.be.false;
    });

    it("should cancel withdrawal and return shares", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);

      await vault.connect(user1).requestWithdraw(shares);
      expect(await vault.balanceOf(user1.address)).to.equal(0);

      await vault.connect(user1).cancelWithdraw();
      expect(await vault.balanceOf(user1.address)).to.equal(shares);
    });

    it("should reject duplicate withdrawal request", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);
      const halfShares = shares / 2n;

      await vault.connect(user1).requestWithdraw(halfShares);

      await expect(
        vault.connect(user1).requestWithdraw(halfShares)
      ).to.be.revertedWithCustomError(vault, "WithdrawalAlreadyPending");
    });

    it("should reject request with insufficient shares", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);

      await expect(
        vault.connect(user1).requestWithdraw(shares + 1n)
      ).to.be.revertedWithCustomError(vault, "InsufficientShares");
    });

    it("should reject cancel when no pending request", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).cancelWithdraw()
      ).to.be.revertedWithCustomError(vault, "NoPendingWithdrawal");
    });

    it("should reject execute when no pending request", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).executeWithdraw()
      ).to.be.revertedWithCustomError(vault, "NoPendingWithdrawal");
    });

    it("should reject zero shares request", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).requestWithdraw(0)
      ).to.be.revertedWithCustomError(vault, "ZeroAmount");
    });
  });

  // ==================== DIRECT WITHDRAW DISABLED ====================

  describe("Direct Withdraw Disabled", function () {
    it("should revert on direct withdraw", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);

      await expect(
        vault.connect(user1).withdraw(usdc(1000), user1.address, user1.address)
      ).to.be.revertedWithCustomError(vault, "DirectWithdrawDisabled");
    });

    it("should revert on direct redeem", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);

      await expect(
        vault.connect(user1).redeem(shares, user1.address, user1.address)
      ).to.be.revertedWithCustomError(vault, "DirectWithdrawDisabled");
    });

    it("should return 0 for maxWithdraw and maxRedeem", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      expect(await vault.maxWithdraw(user1.address)).to.equal(0);
      expect(await vault.maxRedeem(user1.address)).to.equal(0);
    });
  });

  // ==================== STRATEGY FUNCTIONS ====================

  describe("Strategy Functions", function () {
    it("should allow strategist to withdraw and return funds", async function () {
      const { vault, usdcToken, strategist, user1 } =
        await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);

      // Strategist withdraws
      const balBefore = await usdcToken.balanceOf(strategist.address);
      await vault.connect(strategist).withdrawToStrategy(usdc(5000));
      const balAfter = await usdcToken.balanceOf(strategist.address);

      expect(balAfter - balBefore).to.equal(usdc(5000));
      expect(await vault.strategyDebt()).to.equal(usdc(5000));
      expect(await vault.totalAssets()).to.equal(usdc(10_000));

      // Strategist returns same amount (no profit)
      await vault.connect(strategist).depositFromStrategy(usdc(5000));
      expect(await vault.strategyDebt()).to.equal(0);
    });

    it("should distribute performance fee on profit", async function () {
      const { vault, usdcToken, strategist, feeRecipient, user1 } =
        await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);
      await vault.connect(strategist).withdrawToStrategy(usdc(5000));

      // Strategist returns with 1000 USDC profit
      const feeBefore = await usdcToken.balanceOf(feeRecipient.address);
      await vault.connect(strategist).depositFromStrategy(usdc(6000));
      const feeAfter = await usdcToken.balanceOf(feeRecipient.address);

      // 1000 profit * 10% fee = 100 USDC fee
      expect(feeAfter - feeBefore).to.equal(usdc(100));
      expect(await vault.strategyDebt()).to.equal(0);
    });

    it("should handle partial return (loss scenario)", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);
      await vault.connect(strategist).withdrawToStrategy(usdc(5000));

      // Return only 3000 (2000 still deployed)
      await vault.connect(strategist).depositFromStrategy(usdc(3000));
      expect(await vault.strategyDebt()).to.equal(usdc(2000));
    });

    it("should enforce allocation cap", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);

      // Max allocation is 80% = 8000 USDC
      await expect(
        vault.connect(strategist).withdrawToStrategy(usdc(9000))
      ).to.be.revertedWithCustomError(vault, "StrategyAllocationExceeded");

      // 8000 should succeed
      await vault.connect(strategist).withdrawToStrategy(usdc(8000));
    });

    it("should reject non-strategist withdrawal", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);

      await expect(
        vault.connect(user1).withdrawToStrategy(usdc(1000))
      ).to.be.revertedWithCustomError(vault, "AccessControlUnauthorizedAccount");
    });

    it("should reject zero amount strategy operations", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);

      await expect(
        vault.connect(strategist).withdrawToStrategy(0)
      ).to.be.revertedWithCustomError(vault, "ZeroAmount");

      await expect(
        vault.connect(strategist).depositFromStrategy(0)
      ).to.be.revertedWithCustomError(vault, "ZeroAmount");
    });
  });

  // ==================== SHARE PRICE ====================

  describe("Share Price", function () {
    it("should maintain correct share price after profit", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);
      const sharesBefore = await vault.balanceOf(user1.address);

      // Strategist makes 10% profit (net of fee)
      await vault.connect(strategist).withdrawToStrategy(usdc(5000));
      await vault.connect(strategist).depositFromStrategy(usdc(6000));
      // 1000 profit, 100 fee, 900 net to vault

      // Total assets = 5000 (in vault) + 900 (net profit) + 0 (debt cleared) = 5900
      // Wait... let me recalculate:
      // Before strategy: vault has 10000
      // Strategist withdraws 5000: vault has 5000, debt = 5000
      // Strategist returns 6000: vault gets 6000, profit = 1000, fee = 100
      // After: vault balance = 5000 + 6000 - 100 = 10900, debt = 0
      // totalAssets = 10900

      // Total assets should be ~10900 (rounding may cause 1 wei difference)
      const totalAfterProfit = await vault.totalAssets();
      expect(totalAfterProfit).to.be.closeTo(usdc(10_900), 1);
      expect(await vault.balanceOf(user1.address)).to.equal(sharesBefore);

      // Share price increased
      const assetsPerShare = await vault.convertToAssets(sharesBefore);
      expect(assetsPerShare).to.be.closeTo(usdc(10_900), 1);
    });

    it("should keep totalAssets stable during strategy deployment", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);

      const totalBefore = await vault.totalAssets();
      await vault.connect(strategist).withdrawToStrategy(usdc(5000));
      const totalAfter = await vault.totalAssets();

      // totalAssets should remain the same (balance + debt)
      expect(totalAfter).to.equal(totalBefore);
    });
  });

  // ==================== ADMIN FUNCTIONS ====================

  describe("Admin Functions", function () {
    it("should update withdrawal delay", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await vault.connect(admin).setWithdrawalDelay(2 * 24 * 60 * 60);
      expect(await vault.withdrawalDelay()).to.equal(2 * 24 * 60 * 60);
    });

    it("should reject invalid withdrawal delay", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await expect(
        vault.connect(admin).setWithdrawalDelay(60) // 1 min, too short
      ).to.be.revertedWithCustomError(vault, "InvalidWithdrawalDelay");

      await expect(
        vault.connect(admin).setWithdrawalDelay(8 * 24 * 60 * 60) // 8 days, too long
      ).to.be.revertedWithCustomError(vault, "InvalidWithdrawalDelay");
    });

    it("should update performance fee", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await vault.connect(admin).setPerformanceFee(500);
      expect(await vault.performanceFee()).to.equal(500);
    });

    it("should reject performance fee above 20%", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await expect(
        vault.connect(admin).setPerformanceFee(2500)
      ).to.be.revertedWithCustomError(vault, "InvalidPerformanceFee");
    });

    it("should update max strategy allocation", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await vault.connect(admin).setMaxStrategyAllocation(5000);
      expect(await vault.maxStrategyAllocation()).to.equal(5000);
    });

    it("should update fee recipient", async function () {
      const { vault, admin, user1 } = await loadFixture(deployFixture);

      await vault.connect(admin).setFeeRecipient(user1.address);
      expect(await vault.feeRecipient()).to.equal(user1.address);
    });

    it("should reject zero address fee recipient", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await expect(
        vault.connect(admin).setFeeRecipient(ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(vault, "ZeroAddress");
    });

    it("should update deposit limits", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      await vault.connect(admin).setDepositLimits(usdc(10), usdc(50_000));
      expect(await vault.minDeposit()).to.equal(usdc(10));
      expect(await vault.maxDeposit()).to.equal(usdc(50_000));
    });

    it("should reject non-admin calls", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).setWithdrawalDelay(2 * 24 * 60 * 60)
      ).to.be.revertedWithCustomError(vault, "AccessControlUnauthorizedAccount");
    });
  });

  // ==================== PAUSE / UNPAUSE ====================

  describe("Pause / Unpause", function () {
    it("should allow guardian to pause and unpause", async function () {
      const { vault, guardian } = await loadFixture(deployFixture);

      await vault.connect(guardian).pause();
      expect(await vault.paused()).to.be.true;

      await vault.connect(guardian).unpause();
      expect(await vault.paused()).to.be.false;
    });

    it("should block deposits and withdrawal requests when paused", async function () {
      const { vault, guardian, user1 } = await loadFixture(deployFixture);

      await vault.connect(guardian).pause();

      await expect(
        vault.connect(user1).deposit(usdc(1000), user1.address)
      ).to.be.revertedWithCustomError(vault, "EnforcedPause");

      await expect(
        vault.connect(user1).requestWithdraw(1000)
      ).to.be.revertedWithCustomError(vault, "EnforcedPause");
    });

    it("should reject non-guardian pause", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await expect(
        vault.connect(user1).pause()
      ).to.be.revertedWithCustomError(vault, "AccessControlUnauthorizedAccount");
    });
  });

  // ==================== UPGRADE ====================

  describe("Upgrade", function () {
    it("should allow admin to upgrade", async function () {
      const { vault, admin } = await loadFixture(deployFixture);

      const PolyVaultV2 = await ethers.getContractFactory("PolyVault");
      const upgraded = await upgrades.upgradeProxy(
        await vault.getAddress(),
        PolyVaultV2,
        { kind: "uups" }
      );

      expect(await upgraded.getAddress()).to.equal(await vault.getAddress());
      expect(await upgraded.name()).to.equal("PolyVault USDC");
    });

    it("should preserve state after upgrade", async function () {
      const { vault, admin, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const sharesBefore = await vault.balanceOf(user1.address);

      const PolyVaultV2 = await ethers.getContractFactory("PolyVault");
      const upgraded = await upgrades.upgradeProxy(
        await vault.getAddress(),
        PolyVaultV2,
        { kind: "uups" }
      );

      expect(await upgraded.balanceOf(user1.address)).to.equal(sharesBefore);
      expect(await upgraded.totalAssets()).to.equal(usdc(1000));
    });
  });

  // ==================== VIEW FUNCTIONS ====================

  describe("View Functions", function () {
    it("should return correct available balance", async function () {
      const { vault, strategist, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(10_000), user1.address);
      expect(await vault.availableBalance()).to.equal(usdc(10_000));

      await vault.connect(strategist).withdrawToStrategy(usdc(3000));
      expect(await vault.availableBalance()).to.equal(usdc(7000));
    });

    it("should return correct withdrawal request", async function () {
      const { vault, user1 } = await loadFixture(deployFixture);

      await vault.connect(user1).deposit(usdc(1000), user1.address);
      const shares = await vault.balanceOf(user1.address);
      await vault.connect(user1).requestWithdraw(shares);

      const req = await vault.getWithdrawalRequest(user1.address);
      expect(req.shares).to.equal(shares);
      expect(req.pending).to.be.true;
    });
  });
});
