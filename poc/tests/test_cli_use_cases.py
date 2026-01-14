"""CLI use case 테스트

SearchUseCase의 단위 테스트. DB 연결은 모킹하여 테스트.
순환 참조 방지를 위해 모든 프로젝트 import는 테스트 함수 내부에서 수행.
"""
import pytest
from unittest.mock import MagicMock, patch
import argparse
import typing

class TestSearchUseCase:
    """SearchUseCase 테스트"""

    def test_init_creates_pipeline(self):
        """초기화 시 RetrievalPipeline이 생성되는지 확인"""
        # Module must be importable inside test
        import src.rag.cli.use_cases.search as search_module
        
        # patch.object를 사용하여 모듈 내 클래스를 모킹 (AttributeError 방지)
        with patch.object(search_module, "RetrievalPipeline") as MockPipeline:
            from src.rag.cli.use_cases.search import SearchUseCase
            
            mock_embeddings = MagicMock()
            mock_config = MagicMock()
            
            use_case = SearchUseCase(mock_embeddings, mock_config)
            
            MockPipeline.assert_called_once_with(
                mock_embeddings,
                mock_config,
                use_self_query=True,
            )
            assert use_case.pipeline == MockPipeline.return_value

    def test_execute_delegates_to_pipeline(self):
        """execute가 파이프라인에 위임하는지 확인"""
        import src.rag.cli.use_cases.search as search_module
        
        with patch.object(search_module, "RetrievalPipeline") as MockPipeline:
            from src.rag.cli.use_cases.search import SearchUseCase
            
            mock_embeddings = MagicMock()
            mock_config = MagicMock()
            mock_results = [MagicMock(), MagicMock()]
            
            MockPipeline.return_value.retrieve.return_value = mock_results
            
            use_case = SearchUseCase(mock_embeddings, mock_config)
            results = use_case.execute(
                query="test query",
                view="code",
                language="python",
                top_k=5,
                expand_context=True,
            )
            
            MockPipeline.return_value.retrieve.assert_called_once_with(
                query="test query",
                view="code",
                language="python",
                top_k=5,
                expand_context=True,
            )
            assert results == mock_results

    def test_execute_default_parameters(self):
        """기본 파라미터로 execute 호출 확인"""
        import src.rag.cli.use_cases.search as search_module
        
        with patch.object(search_module, "RetrievalPipeline") as MockPipeline:
            from src.rag.cli.use_cases.search import SearchUseCase
            
            mock_embeddings = MagicMock()
            mock_config = MagicMock()
            
            use_case = SearchUseCase(mock_embeddings, mock_config)
            use_case.execute(query="simple query")
            
            MockPipeline.return_value.retrieve.assert_called_once_with(
                query="simple query",
                view=None,
                language=None,
                top_k=10,
                expand_context=True,
            )


class TestIngestResult:
    """IngestResult 데이터클래스 테스트"""

    def test_ingest_result_creation(self):
        """IngestResult 생성 확인"""
        from src.rag.cli.use_cases.ingest import IngestResult
        
        result = IngestResult(
            documents_processed=3,
            concepts_created=10,
            fragments_created=50,
            embeddings_generated=45,
        )
        
        assert result.documents_processed == 3
        assert result.concepts_created == 10
        assert result.fragments_created == 50
        assert result.embeddings_generated == 45


class TestCLIMain:
    """CLI __main__ 테스트"""

    def test_main_function_exists(self):
        """main 함수가 존재하는지 확인"""
        from src.rag.cli.__main__ import main
        
        assert callable(main)

    def test_main_has_return_type_annotation(self):
        """main 함수에 return type annotation이 있는지 확인"""
        from src.rag.cli.__main__ import main
        
        # NoReturn type이어야 함
        hints = typing.get_type_hints(main)
        assert 'return' in hints


class TestCLIParser:
    """CLI parser 테스트"""

    def test_create_parser_returns_parser(self):
        """create_parser가 ArgumentParser를 반환하는지 확인"""
        from src.rag.cli.repl import create_parser
        
        parser = create_parser()
        
        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_has_rag_option(self):
        """파서에 --rag 옵션이 있는지 확인"""
        from src.rag.cli.repl import create_parser
        
        parser = create_parser()
        args = parser.parse_args(["--rag"])
        
        assert args.rag == True

    def test_parser_has_view_option(self):
        """파서에 --view 옵션이 있는지 확인"""
        from src.rag.cli.repl import create_parser
        
        parser = create_parser()
        args = parser.parse_args(["--view", "code"])
        
        assert args.view == "code"
