"""
Tests for data persistence service functionality.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.services.data_persistence import FundDataPersistenceService, DataPersistenceError
from src.models.database import Fund, FundReport, ReportType
from src.parsers.xbrl_parser import (
    FundBasicInfo, AssetAllocation, TopHolding, IndustryAllocation
)


class TestFundDataPersistenceService:
    """Test data persistence service implementation."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value = session
        session.filter.return_value = session
        session.join.return_value = session
        session.first.return_value = None
        session.all.return_value = []
        session.commit.return_value = None
        session.rollback.return_value = None
        session.close.return_value = None
        session.add.return_value = None
        session.flush.return_value = None
        session.delete.return_value = None
        return session
    
    @pytest.fixture
    def service(self, mock_db_session):
        """Create persistence service with mock session."""
        return FundDataPersistenceService(db_session=mock_db_session)
    
    @pytest.fixture
    def sample_fund_info(self):
        """Sample fund basic info for testing."""
        return FundBasicInfo(
            fund_code="000001",
            fund_name="华夏成长混合",
            report_date=datetime(2023, 12, 31),
            net_asset_value=Decimal("15600000000"),
            total_shares=Decimal("12000000000"),
            unit_nav=Decimal("1.3000"),
            accumulated_nav=Decimal("1.4500"),
            fund_manager="张三",
            management_company="华夏基金管理有限公司"
        )
    
    @pytest.fixture
    def sample_asset_allocation(self):
        """Sample asset allocation for testing."""
        return AssetAllocation(
            stock_investments=Decimal("10000000000"),
            stock_ratio=Decimal("0.6410"),
            bond_investments=Decimal("3000000000"),
            bond_ratio=Decimal("0.1923"),
            cash_and_equivalents=Decimal("2600000000"),
            cash_ratio=Decimal("0.1667"),
            total_assets=Decimal("15600000000")
        )
    
    @pytest.fixture
    def sample_top_holdings(self):
        """Sample top holdings for testing."""
        return [
            TopHolding(
                rank=1,
                stock_code="000858",
                stock_name="五粮液",
                market_value=Decimal("800000000"),
                portfolio_ratio=Decimal("0.0513")
            ),
            TopHolding(
                rank=2,
                stock_code="000001",
                stock_name="平安银行",
                market_value=Decimal("750000000"),
                portfolio_ratio=Decimal("0.0481")
            )
        ]
    
    @pytest.fixture
    def sample_industry_allocations(self):
        """Sample industry allocations for testing."""
        return [
            IndustryAllocation(
                industry_name="制造业",
                market_value=Decimal("4500000000"),
                portfolio_ratio=Decimal("0.2885")
            ),
            IndustryAllocation(
                industry_name="金融业",
                market_value=Decimal("3200000000"),
                portfolio_ratio=Decimal("0.2051")
            )
        ]
    
    def test_initialization_with_session(self, mock_db_session):
        """Test service initialization with provided session."""
        service = FundDataPersistenceService(db_session=mock_db_session)
        assert service.db_session == mock_db_session
        assert service._should_close_session is False
    
    def test_initialization_without_session(self):
        """Test service initialization without session."""
        service = FundDataPersistenceService()
        assert service.db_session is None
        assert service._should_close_session is True
    
    def test_context_manager_entry_exit(self, mock_db_session):
        """Test context manager functionality."""
        service = FundDataPersistenceService(db_session=mock_db_session)
        
        with service as s:
            assert s == service
            assert s.db_session == mock_db_session
        
        # Should not call commit/rollback/close for provided session
        mock_db_session.commit.assert_not_called()
        mock_db_session.close.assert_not_called()
    
    @patch('src.services.data_persistence.get_db_session')
    def test_context_manager_without_session(self, mock_get_session):
        """Test context manager when no session is provided."""
        mock_session = MagicMock()
        mock_get_session.return_value = iter([mock_session])
        
        service = FundDataPersistenceService()
        
        with service as s:
            assert s.db_session == mock_session
        
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    def test_save_or_update_fund_new_fund(self, service, sample_fund_info):
        """Test saving new fund."""
        # Mock no existing fund
        service.db_session.query().filter().first.return_value = None
        
        fund = service._save_or_update_fund(sample_fund_info)
        
        assert fund.fund_code == "000001"
        assert fund.fund_name == "华夏成长混合"
        assert fund.management_company == "华夏基金管理有限公司"
        service.db_session.add.assert_called_once()
        service.db_session.flush.assert_called_once()
    
    def test_save_or_update_fund_existing_fund(self, service, sample_fund_info):
        """Test updating existing fund."""
        # Mock existing fund
        existing_fund = Fund(
            id=uuid4(),
            fund_code="000001",
            fund_name="旧名称",
            management_company="旧公司"
        )
        service.db_session.query().filter().first.return_value = existing_fund
        
        fund = service._save_or_update_fund(sample_fund_info)
        
        assert fund == existing_fund
        assert fund.fund_name == "华夏成长混合"
        assert fund.management_company == "华夏基金管理有限公司"
        service.db_session.add.assert_not_called()
    
    def test_check_report_exists_no_report(self, service):
        """Test checking for non-existent report."""
        service.db_session.query().filter().first.return_value = None
        
        result = service._check_report_exists(
            fund_id=str(uuid4()),
            report_date=datetime(2023, 12, 31),
            report_type=ReportType.ANNUAL
        )
        
        assert result is None
    
    def test_check_report_exists_with_report(self, service):
        """Test checking for existing report."""
        existing_report = FundReport(id=uuid4())
        service.db_session.query().filter().first.return_value = existing_report
        
        result = service._check_report_exists(
            fund_id=str(uuid4()),
            report_date=datetime(2023, 12, 31),
            report_type=ReportType.ANNUAL
        )
        
        assert result == existing_report
    
    def test_create_fund_report(self, service, sample_fund_info):
        """Test creating fund report."""
        fund = Fund(id=uuid4(), fund_code="000001")
        
        report = service._create_fund_report(
            fund=fund,
            fund_info=sample_fund_info,
            report_type=ReportType.ANNUAL,
            file_path="test/path.xbrl",
            file_type="XBRL"
        )
        
        assert report.fund_id == fund.id
        assert report.report_type == ReportType.ANNUAL
        assert report.report_year == 2023
        assert report.net_asset_value == sample_fund_info.net_asset_value
        assert report.file_type == "XBRL"
        service.db_session.add.assert_called_once()
        service.db_session.flush.assert_called_once()
    
    def test_get_report_period_annual(self, service):
        """Test getting report period for annual report."""
        period = service._get_report_period(
            datetime(2023, 12, 31),
            ReportType.ANNUAL
        )
        assert period == "年报"
    
    def test_get_report_period_quarterly(self, service):
        """Test getting report period for quarterly report."""
        # Q1
        period = service._get_report_period(
            datetime(2023, 3, 31),
            ReportType.QUARTERLY
        )
        assert period == "Q1"
        
        # Q4
        period = service._get_report_period(
            datetime(2023, 12, 31),
            ReportType.QUARTERLY
        )
        assert period == "Q4"
    
    def test_save_asset_allocation(self, service, sample_asset_allocation):
        """Test saving asset allocation."""
        report = FundReport(id=uuid4())
        
        service._save_asset_allocation(report, sample_asset_allocation)
        
        service.db_session.add.assert_called_once()
        # Verify the asset allocation object was created correctly
        call_args = service.db_session.add.call_args[0][0]
        assert call_args.report_id == report.id
        assert call_args.stock_investments == sample_asset_allocation.stock_investments
    
    def test_save_top_holdings(self, service, sample_top_holdings):
        """Test saving top holdings."""
        report = FundReport(id=uuid4())
        
        service._save_top_holdings(report, sample_top_holdings)
        
        # Should add two holdings
        assert service.db_session.add.call_count == 2
    
    def test_save_industry_allocations(self, service, sample_industry_allocations):
        """Test saving industry allocations."""
        report = FundReport(id=uuid4())
        
        service._save_industry_allocations(report, sample_industry_allocations)
        
        # Should add two industries
        assert service.db_session.add.call_count == 2
    
    def test_save_fund_report_data_success(
        self, service, sample_fund_info, sample_asset_allocation,
        sample_top_holdings, sample_industry_allocations
    ):
        """Test successful fund report data saving."""
        # Mock fund creation
        new_fund = Fund(id=uuid4(), fund_code="000001")
        service.db_session.query().filter().first.side_effect = [None, None]  # No existing fund, no existing report
        
        with patch.object(service, '_save_or_update_fund', return_value=new_fund):
            with patch.object(service, '_create_fund_report') as mock_create_report:
                mock_report = FundReport(id=uuid4())
                mock_create_report.return_value = mock_report
                
                report_id = service.save_fund_report_data(
                    fund_info=sample_fund_info,
                    report_type=ReportType.ANNUAL,
                    file_path="test/path.xbrl",
                    asset_allocation=sample_asset_allocation,
                    top_holdings=sample_top_holdings,
                    industry_allocations=sample_industry_allocations
                )
                
                assert report_id == str(mock_report.id)
                service.db_session.commit.assert_called_once()
    
    def test_save_fund_report_data_existing_report(self, service, sample_fund_info):
        """Test saving when report already exists."""
        existing_fund = Fund(id=uuid4(), fund_code="000001")
        existing_report = FundReport(id=uuid4())
        
        with patch.object(service, '_save_or_update_fund', return_value=existing_fund):
            with patch.object(service, '_check_report_exists', return_value=existing_report):
                
                report_id = service.save_fund_report_data(
                    fund_info=sample_fund_info,
                    report_type=ReportType.ANNUAL,
                    file_path="test/path.xbrl"
                )
                
                assert report_id == str(existing_report.id)
    
    def test_save_fund_report_data_no_session(self, sample_fund_info):
        """Test saving with no database session."""
        service = FundDataPersistenceService(db_session=None)
        
        with pytest.raises(DataPersistenceError) as exc_info:
            service.save_fund_report_data(
                fund_info=sample_fund_info,
                report_type=ReportType.ANNUAL,
                file_path="test/path.xbrl"
            )
        
        assert "数据库会话未初始化" in str(exc_info.value)
    
    def test_check_data_uniqueness_no_session(self):
        """Test uniqueness check with no session."""
        service = FundDataPersistenceService(db_session=None)
        
        result = service.check_data_uniqueness(
            fund_code="000001",
            report_date=datetime(2023, 12, 31),
            report_type=ReportType.ANNUAL
        )
        
        assert result is False
    
    def test_check_data_uniqueness_no_fund(self, service):
        """Test uniqueness check when fund doesn't exist."""
        service.db_session.query().filter().first.return_value = None
        
        result = service.check_data_uniqueness(
            fund_code="000001",
            report_date=datetime(2023, 12, 31),
            report_type=ReportType.ANNUAL
        )
        
        assert result is False
    
    def test_check_data_uniqueness_existing_report(self, service):
        """Test uniqueness check when report exists."""
        existing_fund = Fund(id=uuid4(), fund_code="000001")
        existing_report = FundReport(id=uuid4())
        
        service.db_session.query().filter().first.side_effect = [existing_fund, existing_report]
        
        result = service.check_data_uniqueness(
            fund_code="000001",
            report_date=datetime(2023, 12, 31),
            report_type=ReportType.ANNUAL
        )
        
        assert result is True
    
    def test_get_fund_reports_summary_no_session(self):
        """Test getting summary with no session."""
        service = FundDataPersistenceService(db_session=None)
        
        summary = service.get_fund_reports_summary()
        
        assert summary == {}
    
    def test_get_fund_reports_summary_success(self, service):
        """Test successful summary generation."""
        mock_reports = [
            MagicMock(is_parsed=True, report_type=ReportType.ANNUAL, report_year=2023),
            MagicMock(is_parsed=False, report_type=ReportType.QUARTERLY, report_year=2023),
            MagicMock(is_parsed=True, report_type=ReportType.ANNUAL, report_year=2022)
        ]
        service.db_session.query().join().all.return_value = mock_reports
        
        summary = service.get_fund_reports_summary()
        
        assert summary["total_reports"] == 3
        assert summary["parsed_reports"] == 2
        assert summary["unparsed_reports"] == 1
        assert summary["by_type"]["ANNUAL"] == 2
        assert summary["by_type"]["QUARTERLY"] == 1
        assert summary["by_year"]["2023"] == 2
        assert summary["by_year"]["2022"] == 1
    
    def test_cleanup_failed_reports(self, service):
        """Test cleanup of failed reports."""
        failed_report1 = MagicMock(id=uuid4())
        failed_report2 = MagicMock(id=uuid4())
        
        service.db_session.query().filter().all.return_value = [failed_report1, failed_report2]
        
        count = service.cleanup_failed_reports()
        
        assert count == 2
        service.db_session.commit.assert_called_once()
        assert service.db_session.delete.call_count == 2