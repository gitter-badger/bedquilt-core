import testutils
import json
import psycopg2


class TestListConstraints(testutils.BedquiltTestCase):

    def test_list_constraints(self):
        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(len(result), 0)

        result = self._query("""
        select bq_add_constraints('cool_things', '{}')
        """.format(json.dumps({
            'first_name': {'$required': True}
        })))

        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(len(result), 1)
        self.assertEqual(result, [("first_name:required",)])
        pass

        result = self._query("""
        select bq_add_constraints('cool_things', '{}')
        """.format(json.dumps({
            'first_name': {'$type': 'string'}
        })))

        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(
            result,
            [("first_name:required",),
             ("first_name:type:string",)]
        )

        # add anothe
        result = self._query("""
        select bq_add_constraints('cool_things', '{}')
        """.format(json.dumps({
            'age': {'$notnull': True}
        })))

        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(
            result,
            [("age:notnull",),
             ("first_name:required",),
             ("first_name:type:string",)
             ]
        )

        # remove a constraint
        result = self._query("""
        select bq_remove_constraints('cool_things', '{}')
        """.format(json.dumps({
            'age': {'$notnull': True}
        })))

        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(
            result,
            [("first_name:required",),
             ("first_name:type:string",)]
        )

        # dotted path
        result = self._query("""
        select bq_add_constraints('cool_things', '{}')
        """.format(json.dumps({
            'addresses.0.city': {'$required': True}
        })))

        result = self._query("""
        select bq_list_constraints('cool_things')
        """)
        self.assertEqual(
            result,
            [("addresses.0.city:required",),
             ("first_name:required",),
             ("first_name:type:string",)
             ]
        )


class TestRemoveConstraints(testutils.BedquiltTestCase):

    def test_remove_constraint(self):
        tests = [
            ({'first_name': {'$required': True}},
             {'derp': 1}),
            ({'first_name': {'$notnull': True}},
             {'first_name': None}),
            ({'age': {'$type': 'number'}},
             {'age': ['fish']}),
            ({'first_name': {'$required': True,
                       '$notnull': True,
                       '$type': 'string'},
              'age': {'$type': 'number'}},
             {'first_name': None, 'age': {}})

        ]
        for constraint, example in tests:
            testutils.clean_database(self.conn)
            # remove constraint without even applying it
            result = self._query("""
            select bq_remove_constraints('cool_things', '{}');
            """.format(json.dumps(constraint)))

            self.assertEqual(result, [(False,)])

            # add the constraint
            result = self._query("""
            select bq_add_constraints('cool_things', '{}');
            """.format(json.dumps(constraint)))

            self.assertEqual(result, [(True,)])

            # example should fail to insert
            with self.assertRaises(psycopg2.IntegrityError):
                self.cur.execute("""
                select bq_insert('cool_things', '{}');
                """.format(json.dumps(example)))
            self.conn.rollback()

            # remove the constraint
            result = self._query("""
            select bq_remove_constraints('cool_things', '{}');
            """.format(json.dumps(constraint)))

            self.assertEqual(result, [(True,)])

            # remove again
            result = self._query("""
            select bq_remove_constraints('cool_things', '{}');
            """.format(json.dumps(constraint)))

            self.assertEqual(result, [(False,)])

            # example should insert fine
            result = self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(example)))

            self.assertIsNotNone(result)


class TestAddConstraints(testutils.BedquiltTestCase):

    def test_add_required_constraint(self):
        q = """
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({'first_name': {'$required': True}}))
        result = self._query(q)

        self.assertEqual(result, [(True,)])

        # adding again should be false
        result = self._query(q)

        self.assertEqual(result, [(False,)])

        # should insist on the first_name field being present
        doc = {
            'derp': 1
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self.cur.execute("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should be fine with a first_name key
        doc = {
            'first_name': 'steve',
            'age': 24
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should be fine with a first_name key, even null
        doc = {
            'first_name': None,
            'age': 24
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))

        self.assertIsNotNone(result)

    def test_required_constraint_on_nested_path(self):
        q = """
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'address.city': {'$required': True}
        }))
        result = self._query(q)
        self.assertEqual(result, [(True,)])

        # should reject document where this field is missing
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'baker street'
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should reject document where nested structure is null
        doc = {
            'first_name': 'paul',
            'address': None
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()
        # should accept document where this field is present and null
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'baker street',
                'city': None
            }
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should accept document where this field is present
        # and has value
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'baker street',
                'city': 'london'
            }
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_required_constraint_on_nested_array_path(self):
        q = """
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'stuff.0.first_name': {'$required': True}
        }))
        result = self._query(q)
        self.assertEqual(result, [(True,)])

        # should reject document where nested array is missing
        doc = {
            'first_name': 'paul'
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should reject document where this field is missing
        doc = {
            'first_name': 'paul',
            'cool_things': []
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should accept document where this field is present and null
        doc = {
            'first_name': 'paul',
            'stuff': [
                {'first_name': None}
            ]
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should accept document where this field is present
        # and has value
        doc = {
            'first_name': 'paul',
            'stuff': [
                {'first_name': 'wat'}
            ]
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_notnull_constraint(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'first_name': {'$notnull': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should not reject doc with first_name missing
        doc = {
            'age': 24
        }
        result = self._query("""
        select bq_insert('cool_things', '{}');
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should reject doc with first_name set to null
        doc = {
            'first_name': None,
            'age': 24
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should be fine with a first_name key that is not null
        doc = {
            'first_name': 'steve',
            'age': 24
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_notnull_constraint_on_nested_path(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'address.city': {'$notnull': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should not reject doc with city missing
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'wat'
            }
        }
        result = self._query("""
        select bq_insert('cool_things', '{}');
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should not reject doc with address missing
        doc = {
            'first_name': 'paul',
        }
        result = self._query("""
        select bq_insert('cool_things', '{}');
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should reject doc with city set to null
        doc = {
            'first_name': None,
            'address': {
                'city': None
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

    def test_notnull_constraint_on_nested_array_path(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'addresses.0.city': {'$notnull': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should not reject doc with city missing
        doc = {
            'first_name': 'paul',
            'addresses': [
                {'street': 'wat'}
            ]
        }
        result = self._query("""
        select bq_insert('cool_things', '{}');
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should not reject doc with addresses missing
        doc = {
            'first_name': 'paul',
        }
        result = self._query("""
        select bq_insert('cool_things', '{}');
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should reject doc with city set to null
        doc = {
            'first_name': None,
            'addresses': [
                {'street': 'wat',
                 'city': None}
            ]
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should reject doc with city set to null,
        # but set properly in second element of array
        doc = {
            'first_name': None,
            'addresses': [
                {'street': 'wat',
                 'city': None},
                {'street': 'one',
                 'city': 'wat'}
            ]
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

    def test_required_and_notnull(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'first_name': {'$notnull': 1,
                     '$required': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should reject doc with first_name missing
        doc = {
            'age': 24
        }
        with self.assertRaises(psycopg2.IntegrityError):
            result = self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
            self.assertIsNotNone(result)
        self.conn.rollback()

        # should reject doc with first_name set to null
        doc = {
            'first_name': None,
            'age': 24
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}');
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should be fine with a first_name key that is not null
        doc = {
            'first_name': 'steve',
            'age': 24
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_basic_type_constraint(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'age': {'$type': 'number'}
        })))
        self.assertEqual(result, [(True,)])

        # should reject non-number fields for age
        for val in ['wat', [2], {'wat': 2}, False]:
            doc = {
                'age': val
            }
            with self.assertRaises(psycopg2.IntegrityError):
                self._query("""
                select bq_insert('cool_things', '{}');
                """.format(json.dumps(doc)))
            self.conn.rollback()

        # should be ok if age is a number
        doc = {
            'age': 22
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_type_constraint_on_missing_value(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'age': {'$type': 'number'}
        })))
        self.assertEqual(result, [(True,)])

        # should be ok if the field is absent entirely
        doc = {
            'first_name': 'paul'
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_type_on_null_value(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'age': {'$type': 'number'}
        })))
        self.assertEqual(result, [(True,)])

        # should be ok if the field is null
        doc = {
            'first_name': 'paul',
            'age': None
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

    def test_type_at_nested_path(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'address.city': {'$type': 'string'}
        })))
        self.assertEqual(result, [(True,)])

        # should reject doc where address.city is a number
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'Baker Street',
                'city': 42
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()

    def test_type_at_nested_array_path(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'addresses.0.city': {'$type': 'string'}
        })))
        self.assertEqual(result, [(True,)])

        # should reject doc where address.city is a number
        doc = {
            'first_name': 'paul',
            'addresses': [
                {'street': 'Baker Street',
                 'city': 42}
            ]
        }
        with self.assertRaises(psycopg2.IntegrityError):
            self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
        self.conn.rollback()

        # should accept doc where addresses is empty
        doc = {
            'first_name': 'paul',
            'addresses': []
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should accept doc where addresses is not present
        doc = {
            'first_name': 'paul'
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)

        # should accept doc where city is string
        doc = {
            'first_name': 'paul',
            'addresses': [
                {'city': 'wat'}
            ]
        }
        result = self._query("""
        select bq_insert('cool_things', '{}')
        """.format(json.dumps(doc)))
        self.assertIsNotNone(result)
    def test_type_and_notnull(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'age': {'$type': 'number',
                    '$notnull': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should raise error if the field is null
        doc = {
            'first_name': 'paul',
            'age': None
        }
        with self.assertRaises(psycopg2.IntegrityError):
            result = self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
            self.assertIsNotNone(result)
        self.conn.rollback()

    def test_type_required_and_notnull_at_nested_path(self):
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'address.city': {'$type': 'string',
                             '$required': 1,
                             '$notnull': 1}
        })))
        self.assertEqual(result, [(True,)])

        # should raise error if the field is null
        doc = {
            'first_name': 'paul',
            'address': {
                'city': None
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            result = self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
            self.assertIsNotNone(result)
        self.conn.rollback()

        # should raise error if the field is absent
        doc = {
            'first_name': 'paul',
            'address': {
                'street': 'baker street'
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            result = self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
            self.assertIsNotNone(result)
        self.conn.rollback()

        # should raise error if the field is wrong type
        doc = {
            'first_name': 'paul',
            'address': {
                'city': 42
            }
        }
        with self.assertRaises(psycopg2.IntegrityError):
            result = self._query("""
            select bq_insert('cool_things', '{}')
            """.format(json.dumps(doc)))
            self.assertIsNotNone(result)
        self.conn.rollback()


    def test_contradictory_type_constraints(self):
        # age type is number
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'age': {'$type': 'number'}
        })))
        self.assertEqual(result, [(True,)])

        # then try to set type as string
        with self.assertRaises(psycopg2.InternalError):
            self._query("""
            select bq_add_constraints('cool_things', '{}');
            """.format(json.dumps({
                'age': {'$type': 'string'}
            })))
        self.conn.rollback()

        # should be ok with a constraint on a different field
        result = self._query("""
        select bq_add_constraints('cool_things', '{}');
        """.format(json.dumps({
            'first_name': {'$type': 'string'}
        })))
        self.assertEqual(result, [(True,)])
