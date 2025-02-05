#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Saga Inc.
# Distributed under the terms of the GPL License.

from copy import copy
from typing import List, Optional, TYPE_CHECKING, Any, Dict

from mitosheet.types import ColumnID, ColumnHeader
from mitosheet.code_chunks.code_chunk import CodeChunk
from mitosheet.transpiler.transpile_utils import \
    column_header_list_to_transpiled_code
from mitosheet.code_chunks.step_performers.column_steps.reorder_column_code_chunk import ReorderColumnCodeChunk
from mitosheet.code_chunks.no_op_code_chunk import NoOpCodeChunk

if TYPE_CHECKING:
    from mitosheet.code_chunks.step_performers.column_steps.add_column_code_chunk import AddColumnCodeChunk
    from mitosheet.code_chunks.step_performers.column_steps.rename_columns_code_chunk import RenameColumnsCodeChunk
else:
    AddColumnCodeChunk = Any


class DeleteColumnsCodeChunk(CodeChunk):

    def get_display_name(self) -> str:
        return 'Deleted columns'
    
    def get_description_comment(self) -> str:
        sheet_index = self.get_param('sheet_index')
        column_ids = self.get_param('column_ids')
        column_headers = self.prev_state.column_ids.get_column_headers_by_ids(sheet_index, column_ids)
        return f'Deleted columns {", ".join([str(ch) for ch in column_headers])}'

    def get_code(self) -> List[str]:
        sheet_index = self.get_param('sheet_index')
        column_ids = self.get_param('column_ids')

        df_name = self.post_state.df_names[sheet_index]
        column_headers_list_string = column_header_list_to_transpiled_code(
            [self.prev_state.column_ids.get_column_header_by_id(sheet_index, column_id) for column_id in column_ids]
        )

        return [f'{df_name}.drop({column_headers_list_string}, axis=1, inplace=True)']

    def get_edited_sheet_indexes(self) -> List[int]:
        return [self.get_param('sheet_index')]

    def _combine_right_with_delete_columns_code_chunk(self, other_code_chunk: "DeleteColumnsCodeChunk") -> Optional["DeleteColumnsCodeChunk"]:
        if not self.params_match(other_code_chunk, ['sheet_index']):
            return None

        first_column_ids = self.get_param('column_ids')
        second_column_ids = other_code_chunk.get_param('column_ids')
        all_column_ids = first_column_ids + second_column_ids

        # Use a loop rather than a set so we preserve the order of the columns being deleted
        new_column_ids = []
        for column_id in all_column_ids:
            if column_id not in new_column_ids:
                new_column_ids.append(column_id)

        return DeleteColumnsCodeChunk(
            self.prev_state,
            other_code_chunk.post_state,
            {
                'sheet_index': self.get_param('sheet_index'),
                'column_ids': new_column_ids
            },
            other_code_chunk.execution_data
        )

    def combine_right(self, other_code_chunk: CodeChunk) -> Optional[CodeChunk]:
        if isinstance(other_code_chunk, DeleteColumnsCodeChunk):
            return self._combine_right_with_delete_columns_code_chunk(other_code_chunk)
            
        return None

    def _combine_left_reorder_column_code_chunk(self, other_code_chunk: ReorderColumnCodeChunk) -> Optional["CodeChunk"]:
        if not self.params_match(other_code_chunk, ['sheet_index']):
            return None

        reordered_column_id = other_code_chunk.get_param('column_id')
        column_ids = self.get_param('column_ids')

        if reordered_column_id in column_ids:
            return DeleteColumnsCodeChunk(
                other_code_chunk.prev_state,
                self.post_state,
                self.params,
                self.execution_data
            )

        return None

    def _combine_left_add_column_code_chunk(self, other_code_chunk: "AddColumnCodeChunk") -> Optional["CodeChunk"]:
        if not self.params_match(other_code_chunk, ['sheet_index']):
            return None

        added_column_id = other_code_chunk.get_param('column_id')
        column_ids: List[ColumnID] = self.get_param('column_ids')

        if added_column_id in column_ids:

            # Remove the added column, as we can just skip and no longer need to delete
            new_column_ids = copy(column_ids)
            column_ids.remove(added_column_id)

            # If there's nothing new, then we return a noop
            if len(new_column_ids) == 0:
                return NoOpCodeChunk(
                    other_code_chunk.prev_state,
                    self.post_state,
                    {},
                    {}
                )
            else:
                # Otherwise, just delete what else is deleted in this step
                new_params = {
                    **self.params,
                    'column_ids': new_column_ids
                }

                return DeleteColumnsCodeChunk(
                    other_code_chunk.prev_state,
                    self.post_state,
                    new_params,
                    self.execution_data
                )

        return None

    def _combine_left_rename_columns_code_chunk(self, other_code_chunk: "RenameColumnsCodeChunk") -> Optional["CodeChunk"]:
        if not self.params_match(other_code_chunk, ['sheet_index']):
            return None
        
        column_ids_to_new_column_headers: Dict[ColumnID, ColumnHeader] = other_code_chunk.get_param('column_ids_to_new_column_headers')
        deleted_column_ids: List[ColumnID] = self.get_param('column_ids')

        to_remove_from_rename = []
        for column_id in deleted_column_ids:
            if column_id in column_ids_to_new_column_headers:
                to_remove_from_rename.append(column_id)

        # If there is not any overlap between renamed and deleted, we change nothing
        if len(to_remove_from_rename) == 0:
            return None

        # If we are removing all of the renames, then we can just skip the renames, and 
        # just do the deletes
        if len(to_remove_from_rename) == len(column_ids_to_new_column_headers):    
            return DeleteColumnsCodeChunk(
                other_code_chunk.prev_state,
                self.post_state,
                self.params,
                self.execution_data
            )
        
        # Otherwise, we don't optimize
        return None
        
    def combine_left(self, other_code_chunk: "CodeChunk") -> Optional["CodeChunk"]:
        if isinstance(other_code_chunk, ReorderColumnCodeChunk):
            return self._combine_left_reorder_column_code_chunk(other_code_chunk)
        from mitosheet.code_chunks.step_performers.column_steps.add_column_code_chunk import AddColumnCodeChunk
        if isinstance(other_code_chunk, AddColumnCodeChunk):
            return self._combine_left_add_column_code_chunk(other_code_chunk)
        from mitosheet.code_chunks.step_performers.column_steps.rename_columns_code_chunk import RenameColumnsCodeChunk
        if isinstance(other_code_chunk, RenameColumnsCodeChunk):
            return self._combine_left_rename_columns_code_chunk(other_code_chunk)



        return None