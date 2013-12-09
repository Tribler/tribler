#
# Written by Lipu Fei
#
# This module constains some functions for building simple SQL statements.
#

def buildInsertSqlStatement(table_name, column_tuple):
    column_str = u'(%s' % column_tuple[0]
    for idx in xrange(1, len(column_tuple)):
        column_str += u', %s' % column_tuple[idx]
    column_str += u')'
    value_str = u'?' + u',?' * (len(column_tuple) - 1)

    sql_stmt = u'INSERT INTO %s %s VALUES (%s)'\
            % (table_name, column_str, value_str)

    return sql_stmt

def buildUpdateSqlStatement(table_name, column_tuple, where_column_tuple):
    column_str = u'%s = ?' % column_tuple[0]
    for idx in xrange(1, len(column_tuple)):
        column_str += u', %s = ?' % column_tuple[idx]

    sql_stmt = u'UPDATE %s SET %s' % (table_name, column_str)
    sql_stmt += buildOtherSqlStatement(where_column_tuple)

    return sql_stmt

def buildSelectSqlStatement(table_name, column_tuple,
            where_column_tuple=None, order_by=None, limit=None):
    column_str = u'%s' % column_tuple[0]
    for idx in xrange(1, len(column_tuple)):
        column_str += u', %s' % column_tuple[idx]

    sql_stmt = u'SELECT %s FROM %s' (column_str, table_name)
    sql_stmt += buildOtherSqlStatement(where_column_tuple, order_by, limit)

    return sql_stmt

def buildDeleteSqlStatement(table_name, where_column_tuple):
    sql_stmt = u'DELETE FROM %s' % table_name
    sql_stmt += buildOtherSqlStatement(where_column_tuple)

    return sql_stmt

def buildOtherSqlStatement(where_column_tuple=None, order_by=None, limit=None):
    other_sql_stmt = u''

    # WHERE part
    if where_column_tuple:
        where_stmt = u' WHERE %s = ?' % where_column_tuple[0]
        for idx in xrange(1, len(where_column_tuple)):
            where_stmt += u' AND %s = ?' % where_column_tuple[idx]
        other_sql_stmt += where_stmt

    # ORDER BY part
    if order_by:
        other_sql_stmt += u' ORDER BY %s' % order_by

    # LIMIT part
    if limit:
        other_sql_stmt += u' LIMIT %d' % limit

    return other_sql_stmt