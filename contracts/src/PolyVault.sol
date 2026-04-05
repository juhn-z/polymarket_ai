// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC4626Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC4626Upgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ReentrancyGuardTransient} from "@openzeppelin/contracts/utils/ReentrancyGuardTransient.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @title PolyVault - USDC vault for AI-driven Polymarket prediction trading
/// @notice ERC4626 vault with delayed withdrawal, strategy management and UUPS upgradability
contract PolyVault is
    ERC4626Upgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardTransient,
    UUPSUpgradeable
{
    using SafeERC20 for IERC20;

    // ========== CONSTANTS ==========

    bytes32 public constant STRATEGIST_ROLE = keccak256("STRATEGIST_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    uint256 public constant MIN_WITHDRAWAL_DELAY = 1 hours;
    uint256 public constant MAX_WITHDRAWAL_DELAY = 7 days;
    uint256 public constant MAX_PERFORMANCE_FEE = 2000; // 20%
    uint256 public constant BASIS_POINTS = 10_000;

    // ========== STRUCTS ==========

    struct WithdrawalRequest {
        uint256 shares;
        uint256 requestTimestamp;
        bool pending;
    }

    // ========== STATE ==========

    uint256 public withdrawalDelay;
    mapping(address => WithdrawalRequest) private _withdrawalRequests;

    uint256 public minDeposit;
    uint256 public maxDeposit;

    uint256 public strategyDebt;
    uint256 public maxStrategyAllocation;

    uint256 public performanceFee;
    address public feeRecipient;

    // ========== EVENTS ==========

    event WithdrawalRequested(address indexed user, uint256 shares, uint256 timestamp);
    event WithdrawalExecuted(address indexed user, uint256 shares, uint256 assets);
    event WithdrawalCancelled(address indexed user, uint256 shares);
    event StrategyWithdrawal(address indexed strategist, uint256 amount);
    event StrategyDeposit(address indexed strategist, uint256 amount);
    event ProfitReported(uint256 profit, uint256 fee);
    event PerformanceFeeUpdated(uint256 oldFee, uint256 newFee);
    event WithdrawalDelayUpdated(uint256 oldDelay, uint256 newDelay);
    event MaxStrategyAllocationUpdated(uint256 oldAllocation, uint256 newAllocation);
    event DepositLimitsUpdated(uint256 minDeposit, uint256 maxDeposit);
    event FeeRecipientUpdated(address oldRecipient, address newRecipient);

    // ========== ERRORS ==========

    error DepositBelowMinimum(uint256 amount, uint256 minimum);
    error DepositAboveMaximum(uint256 amount, uint256 maximum);
    error NoPendingWithdrawal();
    error WithdrawalAlreadyPending();
    error WithdrawalDelayNotMet(uint256 currentTime, uint256 availableTime);
    error InsufficientShares(uint256 requested, uint256 available);
    error InvalidWithdrawalDelay(uint256 delay);
    error InvalidPerformanceFee(uint256 fee);
    error InvalidAllocation(uint256 allocation);
    error StrategyAllocationExceeded(uint256 requested, uint256 available);
    error ZeroAddress();
    error ZeroAmount();
    error DirectWithdrawDisabled();

    // ========== CONSTRUCTOR ==========

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    // ========== INITIALIZER ==========

    /// @notice Initialize the vault with all required parameters
    function initialize(
        address _usdc,
        address _admin,
        address _strategist,
        address _guardian,
        address _feeRecipient,
        uint256 _withdrawalDelay,
        uint256 _maxAllocation,
        uint256 _performanceFee
    ) external initializer {
        if (_usdc == address(0) || _admin == address(0) || _feeRecipient == address(0))
            revert ZeroAddress();
        if (_withdrawalDelay < MIN_WITHDRAWAL_DELAY || _withdrawalDelay > MAX_WITHDRAWAL_DELAY)
            revert InvalidWithdrawalDelay(_withdrawalDelay);
        if (_performanceFee > MAX_PERFORMANCE_FEE) revert InvalidPerformanceFee(_performanceFee);
        if (_maxAllocation > BASIS_POINTS) revert InvalidAllocation(_maxAllocation);

        __ERC20_init("PolyVault USDC", "pvUSDC");
        __ERC4626_init(IERC20(_usdc));
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(STRATEGIST_ROLE, _strategist);
        _grantRole(GUARDIAN_ROLE, _guardian);

        withdrawalDelay = _withdrawalDelay;
        maxStrategyAllocation = _maxAllocation;
        performanceFee = _performanceFee;
        feeRecipient = _feeRecipient;

        minDeposit = 1e6; // 1 USDC
        maxDeposit = 100_000e6; // 100,000 USDC
    }

    // ========== ERC4626 DEPOSIT OVERRIDES ==========

    /// @notice Deposit USDC into the vault with limit checks
    function deposit(
        uint256 assets,
        address receiver
    ) public override whenNotPaused nonReentrant returns (uint256) {
        if (assets < minDeposit) revert DepositBelowMinimum(assets, minDeposit);
        if (assets > maxDeposit) revert DepositAboveMaximum(assets, maxDeposit);
        return super.deposit(assets, receiver);
    }

    /// @notice Mint exact shares with limit checks on the required assets
    function mint(
        uint256 shares,
        address receiver
    ) public override whenNotPaused nonReentrant returns (uint256) {
        uint256 assets = previewMint(shares);
        if (assets < minDeposit) revert DepositBelowMinimum(assets, minDeposit);
        if (assets > maxDeposit) revert DepositAboveMaximum(assets, maxDeposit);
        return super.mint(shares, receiver);
    }

    // ========== DISABLE DIRECT WITHDRAW / REDEEM ==========

    /// @notice Direct withdraw is disabled, use requestWithdraw + executeWithdraw
    function withdraw(uint256, address, address) public pure override returns (uint256) {
        revert DirectWithdrawDisabled();
    }

    /// @notice Direct redeem is disabled, use requestWithdraw + executeWithdraw
    function redeem(uint256, address, address) public pure override returns (uint256) {
        revert DirectWithdrawDisabled();
    }

    /// @notice Returns 0 since direct withdraw is disabled
    function maxWithdraw(address) public pure override returns (uint256) {
        return 0;
    }

    /// @notice Returns 0 since direct redeem is disabled
    function maxRedeem(address) public pure override returns (uint256) {
        return 0;
    }

    // ========== DELAYED WITHDRAWAL ==========

    /// @notice Request a delayed withdrawal by locking shares in the vault
    function requestWithdraw(uint256 shares) external whenNotPaused nonReentrant {
        if (shares == 0) revert ZeroAmount();
        if (_withdrawalRequests[msg.sender].pending) revert WithdrawalAlreadyPending();
        if (balanceOf(msg.sender) < shares)
            revert InsufficientShares(shares, balanceOf(msg.sender));

        _transfer(msg.sender, address(this), shares);

        _withdrawalRequests[msg.sender] = WithdrawalRequest({
            shares: shares,
            requestTimestamp: block.timestamp,
            pending: true
        });

        emit WithdrawalRequested(msg.sender, shares, block.timestamp);
    }

    /// @notice Cancel a pending withdrawal and reclaim locked shares
    function cancelWithdraw() external nonReentrant {
        WithdrawalRequest storage req = _withdrawalRequests[msg.sender];
        if (!req.pending) revert NoPendingWithdrawal();

        uint256 shares = req.shares;
        delete _withdrawalRequests[msg.sender];

        _transfer(address(this), msg.sender, shares);

        emit WithdrawalCancelled(msg.sender, shares);
    }

    /// @notice Execute a withdrawal after the delay period has passed
    function executeWithdraw() external nonReentrant {
        WithdrawalRequest storage req = _withdrawalRequests[msg.sender];
        if (!req.pending) revert NoPendingWithdrawal();

        uint256 availableTime = req.requestTimestamp + withdrawalDelay;
        if (block.timestamp < availableTime)
            revert WithdrawalDelayNotMet(block.timestamp, availableTime);

        uint256 requestedShares = req.shares;
        uint256 assets = convertToAssets(requestedShares);
        delete _withdrawalRequests[msg.sender];

        uint256 vaultBalance = IERC20(asset()).balanceOf(address(this));
        uint256 sharesToBurn;
        uint256 assetsToTransfer;

        if (assets <= vaultBalance) {
            sharesToBurn = requestedShares;
            assetsToTransfer = assets;
        } else {
            // Partial withdrawal: vault has insufficient USDC (deployed to strategy)
            assetsToTransfer = vaultBalance;
            sharesToBurn = convertToShares(vaultBalance);
            if (sharesToBurn > requestedShares) {
                sharesToBurn = requestedShares;
            }
            uint256 excessShares = requestedShares - sharesToBurn;
            if (excessShares > 0) {
                _transfer(address(this), msg.sender, excessShares);
            }
        }

        _burn(address(this), sharesToBurn);
        IERC20(asset()).safeTransfer(msg.sender, assetsToTransfer);

        emit WithdrawalExecuted(msg.sender, sharesToBurn, assetsToTransfer);
    }

    // ========== STRATEGY FUNCTIONS ==========

    /// @notice Withdraw USDC from vault to trade on Polymarket
    function withdrawToStrategy(
        uint256 amount
    ) external onlyRole(STRATEGIST_ROLE) nonReentrant {
        if (amount == 0) revert ZeroAmount();

        uint256 maxAllowed = (totalAssets() * maxStrategyAllocation) / BASIS_POINTS;
        if (strategyDebt + amount > maxAllowed) {
            uint256 available = maxAllowed > strategyDebt ? maxAllowed - strategyDebt : 0;
            revert StrategyAllocationExceeded(amount, available);
        }

        strategyDebt += amount;
        IERC20(asset()).safeTransfer(msg.sender, amount);

        emit StrategyWithdrawal(msg.sender, amount);
    }

    /// @notice Return USDC to vault after trading, automatically distributes profit fee
    function depositFromStrategy(
        uint256 amount
    ) external onlyRole(STRATEGIST_ROLE) nonReentrant {
        if (amount == 0) revert ZeroAmount();

        IERC20(asset()).safeTransferFrom(msg.sender, address(this), amount);

        if (amount >= strategyDebt) {
            uint256 profit = amount - strategyDebt;
            strategyDebt = 0;

            if (profit > 0 && performanceFee > 0 && feeRecipient != address(0)) {
                uint256 fee = (profit * performanceFee) / BASIS_POINTS;
                IERC20(asset()).safeTransfer(feeRecipient, fee);
                emit ProfitReported(profit, fee);
            }
        } else {
            strategyDebt -= amount;
        }

        emit StrategyDeposit(msg.sender, amount);
    }

    // ========== TOTAL ASSETS OVERRIDE ==========

    /// @notice Total assets includes USDC in vault + USDC deployed to strategy
    function totalAssets() public view override returns (uint256) {
        return IERC20(asset()).balanceOf(address(this)) + strategyDebt;
    }

    // ========== ADMIN FUNCTIONS ==========

    /// @notice Update the withdrawal delay period
    function setWithdrawalDelay(uint256 _delay) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_delay < MIN_WITHDRAWAL_DELAY || _delay > MAX_WITHDRAWAL_DELAY)
            revert InvalidWithdrawalDelay(_delay);
        uint256 oldDelay = withdrawalDelay;
        withdrawalDelay = _delay;
        emit WithdrawalDelayUpdated(oldDelay, _delay);
    }

    /// @notice Set maximum strategy allocation in basis points
    function setMaxStrategyAllocation(
        uint256 _allocation
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_allocation > BASIS_POINTS) revert InvalidAllocation(_allocation);
        uint256 oldAllocation = maxStrategyAllocation;
        maxStrategyAllocation = _allocation;
        emit MaxStrategyAllocationUpdated(oldAllocation, _allocation);
    }

    /// @notice Set performance fee in basis points (max 20%)
    function setPerformanceFee(uint256 _fee) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_fee > MAX_PERFORMANCE_FEE) revert InvalidPerformanceFee(_fee);
        uint256 oldFee = performanceFee;
        performanceFee = _fee;
        emit PerformanceFeeUpdated(oldFee, _fee);
    }

    /// @notice Set the address that receives performance fees
    function setFeeRecipient(address _recipient) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_recipient == address(0)) revert ZeroAddress();
        address oldRecipient = feeRecipient;
        feeRecipient = _recipient;
        emit FeeRecipientUpdated(oldRecipient, _recipient);
    }

    /// @notice Set min and max deposit limits
    function setDepositLimits(
        uint256 _min,
        uint256 _max
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        minDeposit = _min;
        maxDeposit = _max;
        emit DepositLimitsUpdated(_min, _max);
    }

    /// @notice Pause all deposits and withdrawal requests
    function pause() external onlyRole(GUARDIAN_ROLE) {
        _pause();
    }

    /// @notice Unpause the contract
    function unpause() external onlyRole(GUARDIAN_ROLE) {
        _unpause();
    }

    // ========== UPGRADE ==========

    /// @notice Authorize UUPS upgrade (admin only)
    function _authorizeUpgrade(address) internal override onlyRole(DEFAULT_ADMIN_ROLE) {}

    // ========== VIEW FUNCTIONS ==========

    /// @notice Get the USDC balance available in the vault (excludes strategy debt)
    function availableBalance() public view returns (uint256) {
        return IERC20(asset()).balanceOf(address(this));
    }

    /// @notice Get a user's pending withdrawal request
    function getWithdrawalRequest(
        address user
    ) external view returns (WithdrawalRequest memory) {
        return _withdrawalRequests[user];
    }
}
