// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockOracle {
    int256 private price;
    uint256 public updatedAt;

    event PriceUpdated(int256 price, uint256 updatedAt);

    constructor(int256 initialPrice) {
        price = initialPrice;
        updatedAt = block.timestamp;
    }

    function updatePrice(int256 newPrice) external {
        require(newPrice > 0, "price must be positive");
        price = newPrice;
        updatedAt = block.timestamp;
        emit PriceUpdated(newPrice, block.timestamp);
    }

    function latestPrice() external view returns (int256, uint256) {
        return (price, updatedAt);
    }
}
