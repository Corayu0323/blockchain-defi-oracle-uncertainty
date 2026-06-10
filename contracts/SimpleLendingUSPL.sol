// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IMockOracle {
    function latestPrice() external view returns (int256, uint256);
}

contract SimpleLendingUSPL {
    uint256 public constant WAD = 1e18;

    IMockOracle public oracle;

    mapping(address => uint256) public collateralEth;
    mapping(address => uint256) public debtUsdc;

    uint256 public liquidationThresholdWad = 0.8e18;
    uint256 public liquidationBonusWad = 0.05e18;
    uint256 public uncertaintyWidthWad = 0.04e18;
    uint256 public capMinWad = 0.05e18;
    uint256 public capMaxWad = 0.50e18;
    uint256 public gammaWad = 4e18;

    event Deposited(address indexed borrower, uint256 amountEth);
    event Borrowed(address indexed borrower, uint256 amountUsdc);
    event Liquidated(
        address indexed liquidator,
        address indexed borrower,
        uint256 repaidUsdc,
        uint256 seizedEth,
        string zone,
        uint256 closeCapWad
    );

    constructor(address oracleAddress) {
        oracle = IMockOracle(oracleAddress);
    }

    function depositCollateral() external payable {
        require(msg.value > 0, "no collateral");
        collateralEth[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function borrow(uint256 amountUsdc) external {
        debtUsdc[msg.sender] += amountUsdc;
        require(_healthFactor(msg.sender, _oraclePriceWad()) >= WAD, "unsafe borrow");
        emit Borrowed(msg.sender, amountUsdc);
    }

    function healthFactor(address borrower) external view returns (uint256) {
        return _healthFactor(borrower, _oraclePriceWad());
    }

    function healthFactorInterval(address borrower)
        external
        view
        returns (uint256 hfMin, uint256 hfMax)
    {
        (uint256 priceLow, uint256 priceHigh) = _priceInterval();
        hfMin = _healthFactor(borrower, priceLow);
        hfMax = _healthFactor(borrower, priceHigh);
    }

    function zone(address borrower) public view returns (string memory) {
        (uint256 priceLow, uint256 priceHigh) = _priceInterval();
        uint256 hfMin = _healthFactor(borrower, priceLow);
        uint256 hfMax = _healthFactor(borrower, priceHigh);

        if (hfMin > WAD) {
            return "safe";
        }
        if (hfMax < WAD) {
            return "liquidation";
        }
        return "uncertainty";
    }

    function closeCap(address borrower) public view returns (uint256) {
        string memory z = zone(borrower);
        bytes32 hashed = keccak256(bytes(z));
        if (hashed == keccak256(bytes("safe"))) {
            return 0;
        }
        if (hashed == keccak256(bytes("liquidation"))) {
            return capMaxWad;
        }

        uint256 uncertaintyIntensityWad = 2 * uncertaintyWidthWad;
        uint256 penalty = (gammaWad * uncertaintyIntensityWad) / WAD;
        if (penalty >= capMaxWad) {
            return capMinWad;
        }
        uint256 cap = capMaxWad - penalty;
        if (cap < capMinWad) {
            return capMinWad;
        }
        return cap;
    }

    function liquidate(address borrower) external {
        uint256 capWad = closeCap(borrower);
        require(capWad > 0, "not liquidatable");
        require(debtUsdc[borrower] > 0, "no debt");

        uint256 repayUsdc = (debtUsdc[borrower] * capWad) / WAD;
        uint256 priceWad = _oraclePriceWad();
        uint256 seizeEth = (repayUsdc * WAD * (WAD + liquidationBonusWad)) / priceWad / WAD;

        if (seizeEth > collateralEth[borrower]) {
            seizeEth = collateralEth[borrower];
        }
        if (repayUsdc > debtUsdc[borrower]) {
            repayUsdc = debtUsdc[borrower];
        }

        debtUsdc[borrower] -= repayUsdc;
        collateralEth[borrower] -= seizeEth;

        emit Liquidated(msg.sender, borrower, repayUsdc, seizeEth, zone(borrower), capWad);
    }

    function _oraclePriceWad() internal view returns (uint256) {
        (int256 price, ) = oracle.latestPrice();
        require(price > 0, "bad oracle price");
        return uint256(price);
    }

    function _priceInterval() internal view returns (uint256 priceLow, uint256 priceHigh) {
        uint256 price = _oraclePriceWad();
        priceLow = (price * (WAD - uncertaintyWidthWad)) / WAD;
        priceHigh = (price * (WAD + uncertaintyWidthWad)) / WAD;
    }

    function _healthFactor(address borrower, uint256 priceWad) internal view returns (uint256) {
        uint256 debt = debtUsdc[borrower];
        if (debt == 0) {
            return type(uint256).max;
        }
        uint256 collateralValue = (collateralEth[borrower] * priceWad) / WAD;
        return (collateralValue * liquidationThresholdWad) / debt;
    }
}
