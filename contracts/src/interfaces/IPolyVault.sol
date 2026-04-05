// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC4626} from "@openzeppelin/contracts/interfaces/IERC4626.sol";

/// @title IPolyVault - Interface for the PolyVault USDC vault
/// @notice Extends ERC4626 with delayed withdrawal, strategy management and role-based access
interface IPolyVault is IERC4626 {
    // ========== STRUCTS ==========

    struct WithdrawalRequest {
        uint256 shares;
        uint256 requestTimestamp;
        bool pending;
    }

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

    // ========== DELAYED WITHDRAWAL ==========

    /// @notice Request a delayed withdrawal by locking shares in the vault
    function requestWithdraw(uint256 shares) external;

    /// @notice Cancel a pending withdrawal and reclaim locked shares
    function cancelWithdraw() external;

    /// @notice Execute a withdrawal after the delay period has passed
    function executeWithdraw() external;

    // ========== STRATEGY ==========

    /// @notice Withdraw USDC from vault to trade on Polymarket (strategist only)
    function withdrawToStrategy(uint256 amount) external;

    /// @notice Return USDC to vault after trading, auto-distributes profit fee
    function depositFromStrategy(uint256 amount) external;

    // ========== ADMIN ==========

    /// @notice Update the withdrawal delay period
    function setWithdrawalDelay(uint256 delay) external;

    /// @notice Set maximum strategy allocation in basis points
    function setMaxStrategyAllocation(uint256 allocation) external;

    /// @notice Set performance fee in basis points (max 20%)
    function setPerformanceFee(uint256 fee) external;

    /// @notice Set the address that receives performance fees
    function setFeeRecipient(address recipient) external;

    /// @notice Set min and max deposit limits
    function setDepositLimits(uint256 min, uint256 max) external;

    // ========== VIEW ==========

    /// @notice Get the USDC balance available in the vault (excludes strategy debt)
    function availableBalance() external view returns (uint256);

    /// @notice Get a user's pending withdrawal request
    function getWithdrawalRequest(address user) external view returns (WithdrawalRequest memory);

    /// @notice Current amount of USDC deployed to strategy
    function strategyDebt() external view returns (uint256);

    /// @notice Current withdrawal delay in seconds
    function withdrawalDelay() external view returns (uint256);

    /// @notice Max strategy allocation in basis points
    function maxStrategyAllocation() external view returns (uint256);

    /// @notice Performance fee in basis points
    function performanceFee() external view returns (uint256);

    /// @notice Address that receives performance fees
    function feeRecipient() external view returns (address);
}
