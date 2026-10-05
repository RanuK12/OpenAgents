const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MultiTokenStaking", function () {
  let multiTokenStaking;
  let tokenA, tokenB;
  let owner, user;
  const AMOUNT_A = ethers.utils.parseEther("100");
  const AMOUNT_B = ethers.utils.parseEther("200");

  beforeEach(async function () {
    [owner, user] = await ethers.getSigners();

    // Deploy mock ERC20 tokens
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    tokenA = await MockERC20.deploy("Token A", "TKA", AMOUNT_A.mul(10)); // 1000 total
    tokenB = await MockERC20.deploy("Token B", "TKB", AMOUNT_B.mul(10));
    await tokenA.deployed();
    await tokenB.deployed();

    // Deploy MultiTokenStaking with a dummy reward token (we won't use rewards)
    const RewardToken = await ethers.getContractFactory("MockERC20");
    const rewardToken = await RewardToken.deploy("Reward", "RWD", ethers.utils.parseEther("10000"));
    await rewardToken.deployed();

    const MultiTokenStaking = await ethers.getContractFactory("MultiTokenStaking");
    multiTokenStaking = await MultiTokenStaking.deploy(rewardToken.address, 0); // rewardPerSecond = 0
    await multiTokenStaking.deployed();

    // Give user some tokens
    await tokenA.transfer(user.address, AMOUNT_A);
    await tokenB.transfer(user.address, AMOUNT_B);
  });

  it("should allow emergencyWithdraw to withdraw all staked tokens without penalties", async function () {
    // Approve and deposit token A
    await tokenA.connect(user).approve(multiTokenStaking.address, AMOUNT_A);
    await multiTokenStaking.connect(user).deposit(0, AMOUNT_A); // pool 0 will be tokenA after we add pools

    // Approve and deposit token B
    await tokenB.connect(user).approve(multiTokenStaking.address, AMOUNT_B);
    await multiTokenStaking.connect(user).deposit(1, AMOUNT_B); // pool 1 tokenB

    // Add pools (owner)
    await multiTokenStaking.connect(owner).addPool(100, tokenA.address); // pid 0
    await multiTokenStaking.connect(owner).addPool(200, tokenB.address); // pid 1

    // Check user staked balances before emergencyWithdraw
    let userInfoA = await multiTokenStaking.userInfo(0, user.address);
    let userInfoB = await multiTokenStaking.userInfo(1, user.address);
    expect(userInfoA.amount).to.equal(AMOUNT_A);
    expect(userInfoB.amount).to.equal(AMOUNT_B);

    // Check contract token balances before
    let contractBalanceA = await tokenA.balanceOf(multiTokenStaking.address);
    let contractBalanceB = await tokenB.balanceOf(multiTokenStaking.address);
    expect(contractBalanceA).to.equal(AMOUNT_A);
    expect(contractBalanceB).to.equal(AMOUNT_B);

    // Call emergencyWithdraw
    const tx = await multiTokenStaking.connect(user).emergencyWithdraw();
    const receipt = await tx.wait();

    // Check that EmergencyWithdraw event was emitted
    const event = receipt.events.find(e => e.event === "EmergencyWithdraw");
    expect(event).to.exist;
    const amounts = event.args.amounts;
    expect(amounts.length).to.equal(2);
    expect(amounts[0]).to.equal(AMOUNT_A);
    expect(amounts[1]).to.equal(AMOUNT_B);

    // Check user staked balances after
    userInfoA = await multiTokenStaking.userInfo(0, user.address);
    userInfoB = await multiTokenStaking.userInfo(1, user.address);
    expect(userInfoA.amount).to.equal(0);
    expect(userInfoB.amount).to.equal(0);

    // Check user token balances after (should have received tokens)
    expect(await tokenA.balanceOf(user.address)).to.equal(AMOUNT_A); // started with AMOUNT_A, deposited, now withdrawn
    expect(await tokenB.balanceOf(user.address)).to.equal(AMOUNT_B);

    // Check contract token balances after (should be zero)
    contractBalanceA = await tokenA.balanceOf(multiTokenStaking.address);
    contractBalanceB = await tokenB.balanceOf(multiTokenStaking.address);
    expect(contractBalanceA).to.equal(0);
    expect(contractBalanceB).to.equal(0);

    // Ensure no PenaltyPaid event was emitted (if such event existed)
    const penaltyEvent = receipt.events.find(e => e.event === "PenaltyPaid");
    expect(penaltyEvent).to.not.exist;
  });
});