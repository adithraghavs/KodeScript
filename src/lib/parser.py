from lib.utils import token, nodes
from lib import errors

#######################################
# PARSE RESULT
#######################################

class ParseResult:
	def __init__(self):
		self.error = None
		self.node = None
		self.last_registered_advance_count = 0
		self.advanced_count = 0
		self.to_reverse_count = 0

	def register_advancement(self):
		self.advanced_count += 1
		self.last_registered_advance_count += 1

	def register(self, res):
		self.last_registered_advance_count = res.advanced_count
		self.advanced_count += res.advanced_count
		if res.error: self.error = res.error
		return res.node

	def try_register(self, res):
		if res.error:
			self.to_reverse_count = res.advanced_count
			return None
		return self.register(res)

	def success(self, node):
		self.node = node
		return self

	def failure(self, error):
		if not self.error or self.advanced_count == 0:
			self.error = error
		return self

#######################################
# PARSER
#######################################

class Parser:
	def __init__(self, tokens):
		self.tokens = tokens
		self.tok_idx = -1
		self.advance()

	def advance(self):
		self.tok_idx += 1
		self.update_current_tok()
		return self.current_tok

	def reverse(self, amount=1):
		self.tok_idx -= amount
		self.update_current_tok()
		return self.current_tok

	def update_current_tok(self):
		if self.tok_idx >= 0 and self.tok_idx < len(self.tokens):
			self.current_tok = self.tokens[self.tok_idx]

	def parse(self):
		if len(self.tokens) == 1 and self.tokens[0].type == token.T_EOF:
			return ParseResult().success(nodes.ListNode([], self.tokens[0].pos_start, self.tokens[0].pos_end))

		res = self.statements()
		if not res.error and self.current_tok.type != token.T_EOF:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected '+', '-', '*' or '/'"
			))
		return res

	###################################

	def statements(self):
		res = ParseResult()
		statements = []
		pos_start = self.current_tok.pos_start.copy()

		while self.current_tok.type == token.T_NEWLINE:
			res.register_advancement()
			self.advance()

		statement = res.register(self.statement())
		if res.error: return res
		statements.append(statement)

		more_statements = True

		while True:
			newline_count = 0
			while self.current_tok.type == token.T_NEWLINE:
				res.register_advancement()
				self.advance()
				newline_count += 1
			if newline_count == 0:
				more_statements = False

			if not more_statements: break
			statement = res.try_register(self.statement())
			if not statement:
				self.reverse(res.to_reverse_count)
				more_statements = False
				continue
			statements.append(statement)

		return res.success(nodes.ListNode(
			statements, pos_start, self.current_tok.pos_end.copy()
		))


	def statement(self):
		res = ParseResult()
		pos_start = self.current_tok.pos_start.copy()

		if self.current_tok.matches(token.T_KEYWORD, 'return'):
			res.register_advancement()
			self.advance()

			expr = res.try_register(self.expr())
			if not expr:
				self.reverse(res.to_reverse_count)
			return res.success(nodes.ReturnNode(expr, pos_start, self.current_tok.pos_end.copy()))

		if self.current_tok.matches(token.T_KEYWORD, 'continue'):
			res.register_advancement()
			self.advance()
			return res.success(nodes.ContinueNode(pos_start, self.current_tok.pos_end.copy()))

		if self.current_tok.matches(token.T_KEYWORD, 'break'):
			res.register_advancement()
			self.advance()
			return res.success(nodes.BreakNode(pos_start, self.current_tok.pos_end.copy()))

		expr = res.register(self.expr())
		if res.error:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected 'break', 'continue', 'return', 'var', 'if', 'for', 'while', 'func', int, float, identifier, '+', '-', '(', ')' '[' or 'not'"
			))

		return res.success(expr)


	def call(self):
		res = ParseResult()

		atom = res.register(self.atom())
		if res.error: return res

		if self.current_tok.type == token.T_LPAREN:
			res.register_advancement()
			self.advance()
			arg_nodes = []
			optional_arg_name_nodes = []
			optional_arg_value_nodes = []

			if self.current_tok.type == token.T_RPAREN:
				res.register_advancement()
				self.advance()
			else:
				arg_nodes.append(res.register(self.expr()))
				if res.error:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected ')', 'var', 'if', 'for', 'while', 'func', int, float, identifier, '+', '-', '(', '[' or 'not'"
					))

				while self.current_tok.type == token.T_COMMA:
					res.register_advancement()
					self.advance()

					arg_nodes.append(res.register(self.expr()))
					if res.error: return res

				if self.current_tok.type == token.T_EQ:
					ident = arg_nodes.pop(-1)
					if type(ident) != nodes.VarAccessNode:
						return res.failure(errors.InvalidSyntaxError(
							self.current_tok.pos_start, self.current_tok.pos_end,
							"Expected an identifier"
						))

					optional_arg_name_nodes.append(ident.var_name_tok)

					res.register_advancement()
					self.advance()

					optional_arg_value_nodes.append(res.register(self.expr()))
					if res.error:
						return res.failure(errors.InvalidSyntaxError(
							self.current_tok.pos_start, self.current_tok.pos_end,
							"Expected int, float, string or boolean"
						))

					while self.current_tok.type == token.T_COMMA:
						res.register_advancement()
						self.advance()

						if self.current_tok.type != token.T_IDENTIFIER:
							return res.failure(errors.InvalidSyntaxError(
								self.current_tok.pos_start, self.current_tok.pos_end,
								f"Expected identifier"
							))

						optional_arg_name_nodes.append(self.current_tok)
						res.register_advancement()
						self.advance()

						if self.current_tok.type != token.T_EQ:
							return res.failure(errors.InvalidSyntaxError(
								self.current_tok.pos_start, self.current_tok.pos_end,
								f"Expected ="
							))

						res.register_advancement()
						self.advance()

						value = res.register(self.atom())
						if res.error: return res

						optional_arg_value_nodes.append(value)


				if self.current_tok.type != token.T_RPAREN:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected ',' or ')'"
					))

				res.register_advancement()
				self.advance()

				
			return res.success(nodes.CallNode(atom, arg_nodes, optional_arg_name_nodes, optional_arg_value_nodes))
		return res.success(atom)


	def atom(self):
		res = ParseResult()
		tok = self.current_tok

		if tok.type in (token.T_INT, token.T_FLOAT):
			res.register_advancement()
			self.advance()
			return res.success(nodes.NumberNode(tok))

		elif tok.type in (token.T_STRING):
			res.register_advancement()
			self.advance()
			return res.success(nodes.StringNode(tok))

		elif tok.type == token.T_IDENTIFIER:
			module = None
			identifier = self.current_tok
			res.register_advancement()
			self.advance()

			if self.current_tok.type == token.T_DOT:
				res.register_advancement()
				self.advance()
				if self.current_tok.type != token.T_IDENTIFIER:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected an identifier"
					))
				
				module = identifier
				identifier = self.current_tok

				res.register_advancement()
				self.advance()
			return res.success(nodes.VarAccessNode(identifier, module))

		elif tok.type == token.T_LPAREN:
			res.register_advancement()
			self.advance()
			expr = res.register(self.expr())
			if res.error: return res
			if self.current_tok.type == token.T_RPAREN:
				res.register_advancement()
				self.advance()
				return res.success(expr)
			else:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ')'"
				))

		elif tok.type == token.T_LSQUARE:
			list_expr = res.register(self.list_expr())
			if res.error: return res
			return res.success(list_expr)

		elif tok.type == token.T_LCURLY:
			dict_expr = res.register(self.dict_expr())
			if res.error: return res
			return res.success(dict_expr)

		elif tok.matches(token.T_KEYWORD, 'if'):
			if_expr = res.register(self.if_expr())
			if res.error: return res
			return res.success(if_expr)

		elif tok.matches(token.T_KEYWORD, 'for'):
			for_expr = res.register(self.for_expr())
			if res.error: return res
			return res.success(for_expr)

		elif tok.matches(token.T_KEYWORD, 'while'):
			while_expr = res.register(self.while_expr())
			if res.error: return res
			return res.success(while_expr)

		elif tok.matches(token.T_KEYWORD, 'func'):
			func_def = res.register(self.func_def())
			if res.error: return res
			return res.success(func_def)

		return res.failure(errors.InvalidSyntaxError(
			tok.pos_start, tok.pos_end,
			"Expected int or float, identifier, '+', '-' or '(', , '[', 'if', 'for', 'while' or 'func'"
		))

	def power(self):
		return self.bin_op(self.call, (token.T_POW, ), self.factor)

	def dict_expr(self):
		res = ParseResult()
		element_nodes = {}
		pos_start = self.current_tok.pos_start.copy()

		if self.current_tok.type != token.T_LCURLY:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected '{'"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_RCURLY:
			res.register_advancement()
			self.advance()
		else:
			key = res.register(self.expr())
			if res.error:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected string"
				))
			
			if not isinstance(key, nodes.StringNode):
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					f"Expected string"
				))

			if self.current_tok.type != token.T_COLON:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					f"Expected ':'"
				))

			res.register_advancement()
			self.advance()

			value = res.register(self.expr())
			if res.error:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected 'var', 'if', 'for', 'while', 'func', int, float, identifier, '+', '-', '(', '[' or 'not'"
				))

			element_nodes[key] = value

			while self.current_tok.type == token.T_COMMA:
				added = False
				res.register_advancement()
				self.advance()

				key = res.register(self.expr())
				if res.error:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected string"
					))
				
				if not isinstance(key, nodes.StringNode):
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						f"Expected string"
					))

				if self.current_tok.type != token.T_COLON:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						f"Expected ':'"
					))

				res.register_advancement()
				self.advance()

				value = res.register(self.expr())
				if res.error:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected 'var', 'if', 'for', 'while', 'func', int, float, identifier, '+', '-', '(', '[' or 'not'"
					))

				for i in element_nodes:
					if i.tok.value == key.tok.value:
						added = True
						element_nodes[i] = value
				
				if not added:
					element_nodes[key] = value

				added = False

			if self.current_tok.type != token.T_RCURLY:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ',' or '}'"
				))

			res.register_advancement()
			self.advance()

		return res.success(nodes.DictNode(
			element_nodes, pos_start, self.current_tok.pos_end.copy()
		))
		

	def list_expr(self):
		res = ParseResult()
		element_nodes = []
		pos_start = self.current_tok.pos_start.copy()

		if self.current_tok.type != token.T_LSQUARE:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected '['"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_RSQUARE:
			res.register_advancement()
			self.advance()
		else:
			element_nodes.append(res.register(self.expr()))
			if res.error:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ']', 'var', 'if', 'for', 'while', 'func', int, float, identifier, '+', '-', '(', '[' or 'not'"
				))

			while self.current_tok.type == token.T_COMMA:
				res.register_advancement()
				self.advance()

				element_nodes.append(res.register(self.expr()))
				if res.error: return res

			if self.current_tok.type != token.T_RSQUARE:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ',' or ']'"
				))

			res.register_advancement()
			self.advance()
		return res.success(nodes.ListNode(
			element_nodes, pos_start, self.current_tok.pos_end.copy()
		))


	def factor(self):
		res = ParseResult()
		tok = self.current_tok

		if tok.type in (token.T_PLUS, token.T_MINUS):
			res.register_advancement()
			self.advance()
			factor = res.register(self.factor())
			if res.error: return res
			return res.success(nodes.UnaryOpNode(tok, factor))

		return self.power()

	def term(self):
		return self.bin_op(self.factor, (token.T_MUL, token.T_DIV, token.T_INT_DIV, token.T_REMAINDER))

	def arithm_expr(self):
		return self.bin_op(self.term, (token.T_PLUS, token.T_MINUS))

	def comp_expr(self):
		res = ParseResult()

		if self.current_tok.matches(token.T_KEYWORD, 'not'):
			op_tok = self.current_tok
			res.register_advancement()
			self.advance()

			node = res.register(self.comp_expr())
			if res.error: return res
			return res.success(nodes.UnaryOpNode(op_tok, node))

		node = res.register(self.bin_op(self.arithm_expr, (token.T_EE, token.T_NE, token.T_LT, token.T_GT, token.T_LTE, token.T_GTE)))

		if res.error:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected int or float, identifier, '+', '-', '(', '[' or 'not'"
			))

		return res.success(node)

	def expr(self):
		res = ParseResult()

		if self.current_tok.matches(token.T_KEYWORD, 'var'):
			res.register_advancement()
			self.advance()
		
			if self.current_tok.type != token.T_IDENTIFIER:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected identifier"
				))

			var_name = self.current_tok
			res.register_advancement()
			self.advance()

			if self.current_tok.type != token.T_EQ:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected '='"
				))

			res.register_advancement()
			self.advance()
			expr = res.register(self.expr())

			if res.error: return res
			return res.success(nodes.VarAssignNode(var_name, expr))

		node = res.register(self.bin_op(self.comp_expr, ((token.T_KEYWORD, 'and'), (token.T_KEYWORD, 'or'))))

		if res.error:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected int or float, identifier, 'var', 'if', 'for', 'while', 'func', '+', '-', '(' or '['"
			))

		return res.success(node)

	def if_expr(self):
		res = ParseResult()
		all_cases = res.register(self.if_expr_cases('if'))
		if res.error: return res
		cases, else_case = all_cases
		return res.success(nodes.IfNode(cases, else_case))

	def if_expr_cases(self, case_keyword):
		res = ParseResult()
		cases = []
		else_case = None

		if not self.current_tok.matches(token.T_KEYWORD, case_keyword):
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected '{case_keyword}'"
			))

		res.register_advancement()
		self.advance()

		condition = res.register(self.expr())
		if res.error: return res

		if not self.current_tok.type == token.T_COLON:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected ':'"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_NEWLINE:
			res.register_advancement()
			self.advance()

			statements = res.register(self.statements())
			if res.error: return res
			cases.append((condition, statements, True))

			if self.current_tok.matches(token.T_KEYWORD, 'end'):
				res.register_advancement()
				self.advance()
			else:
				all_cases = res.register(self.if_expr_b_or_c())
				if res.error: return res
				new_cases, else_case = all_cases
				cases.extend(new_cases)
		else:
			expr = res.register(self.statement())
			if res.error: return res
			cases.append((condition, expr, False))

			all_cases = res.register(self.if_expr_b_or_c())
			if res.error: return res
			new_cases, else_case = all_cases
			cases.extend(new_cases)

		return res.success((cases, else_case))

	def if_expr_b(self):
		return self.if_expr_cases('elif')
    
	def if_expr_c(self):
		res = ParseResult()
		else_case = None

		if self.current_tok.matches(token.T_KEYWORD, 'else'):
			res.register_advancement()
			self.advance()

			if self.current_tok.type != token.T_COLON:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ':'"
				))

			res.register_advancement()
			self.advance()

			if self.current_tok.type == token.T_NEWLINE:
				res.register_advancement()
				self.advance()

				statements = res.register(self.statements())
				if res.error: return res
				else_case = (statements, True)

				if self.current_tok.matches(token.T_KEYWORD, 'end'):
					res.register_advancement()
					self.advance()
				else:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						"Expected 'end'"
					))
			else:
				expr = res.register(self.statement())
				if res.error: return res
				else_case = (expr, False)

		return res.success(else_case)

	def if_expr_b_or_c(self):
		res = ParseResult()
		cases, else_case = [], None

		if self.current_tok.matches(token.T_KEYWORD, 'elif'):
			all_cases = res.register(self.if_expr_b())
			if res.error: return res
			cases, else_case = all_cases
		else:
			else_case = res.register(self.if_expr_c())
			if res.error: return res
    
		return res.success((cases, else_case))


	def for_expr(self):
		res = ParseResult()

		if not self.current_tok.matches(token.T_KEYWORD, 'for'):
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected 'for'"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type != token.T_IDENTIFIER:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected identifier"
			))

		var_name = self.current_tok
		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_EQ:
			res.register_advancement()
			self.advance()

			start_value = res.register(self.expr())
			if res.error: return res

			if not self.current_tok.matches(token.T_KEYWORD, 'to'):
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					f"Expected 'to'"
				))
			
			res.register_advancement()
			self.advance()

			end_value = res.register(self.expr())
			if res.error: return res

			if self.current_tok.matches(token.T_KEYWORD, 'step'):
				res.register_advancement()
				self.advance()

				step_value = res.register(self.expr())
				if res.error: return res
			else:
				step_value = None

			if not self.current_tok.type == token.T_COLON:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ':'"
				))

			res.register_advancement()
			self.advance()

			if self.current_tok.type == token.T_NEWLINE:
				res.register_advancement()
				self.advance()

				body = res.register(self.statements())
				if res.error: return res

				if not self.current_tok.matches(token.T_KEYWORD, 'end'):
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						f"Expected 'end'"
					))

				res.register_advancement()
				self.advance()

				return res.success(nodes.ForNode(var_name, start_value, end_value, step_value, body, True))
			
			body = res.register(self.statement())
			if res.error: return res

			return res.success(nodes.ForNode(var_name, start_value, end_value, step_value, body, False))
		elif self.current_tok.matches(token.T_KEYWORD, 'in'):
			res.register_advancement()
			self.advance()

			array = res.register(self.expr())
			if res.error: return res

			if not self.current_tok.type == token.T_COLON:
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					"Expected ':'"
				))

			res.register_advancement()
			self.advance()

			if self.current_tok.type == token.T_NEWLINE:
				res.register_advancement()
				self.advance()

				body = res.register(self.statements())
				if res.error: return res

				if not self.current_tok.matches(token.T_KEYWORD, 'end'):
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						f"Expected 'end'"
					))

				res.register_advancement()
				self.advance()

				return res.success(nodes.ForEachNode(var_name, array, body, True))
			
			body = res.register(self.statement())
			if res.error: return res

			return res.success(nodes.ForNode(var_name, start_value, end_value, step_value, body, False))
		else:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected '='"
			))


	def while_expr(self):
		res = ParseResult()

		if not self.current_tok.matches(token.T_KEYWORD, 'while'):
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected 'while'"
			))

		res.register_advancement()
		self.advance()

		condition = res.register(self.expr())
		if res.error: return res

		if not self.current_tok.type == token.T_COLON:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected ':'"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_NEWLINE:
			res.register_advancement()
			self.advance()

			body = res.register(self.statements())
			if res.error: return res

			if not self.current_tok.matches(token.T_KEYWORD, 'end'):
				return res.failure(errors.InvalidSyntaxError(
					self.current_tok.pos_start, self.current_tok.pos_end,
					f"Expected 'end'"
				))

			res.register_advancement()
			self.advance()

			return res.success(nodes.WhileNode(condition, body, True))
		
		body = res.register(self.statement())
		if res.error: return res

		return res.success(nodes.WhileNode(condition, body, False))

	def func_def(self):
		res = ParseResult()

		if not self.current_tok.matches(token.T_KEYWORD, 'func'):
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected 'func'"
			))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_IDENTIFIER:
			var_name_tok = self.current_tok
			res.register_advancement()
			self.advance()
			if self.current_tok.type != token.T_LPAREN:
				return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected '('"
				))
		else:
			var_name_tok = None
			if self.current_tok.type != token.T_LPAREN:
				return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected identifier or '('"
				))
    
		res.register_advancement()
		self.advance()
		arg_name_toks = []
		optional_arg_name_tokens = []
		optional_arg_values_tokens = []

		if self.current_tok.type == token.T_IDENTIFIER:
			arg_name_toks.append(self.current_tok)
			res.register_advancement()
			self.advance()
      
			while self.current_tok.type == token.T_COMMA:
				res.register_advancement()
				self.advance()

				if self.current_tok.type != token.T_IDENTIFIER:
					return res.failure(errors.InvalidSyntaxError(
						self.current_tok.pos_start, self.current_tok.pos_end,
						f"Expected identifier"
					))

				arg_name_toks.append(self.current_tok)
				res.register_advancement()
				self.advance()

			if self.current_tok.type == token.T_EQ:
				res.register_advancement()
				self.advance()
				optional_arg_name_tokens.append(arg_name_toks.pop(-1))

				value = res.register(self.atom())
				if res.error: return res

				optional_arg_values_tokens.append(value)

				while self.current_tok.type == token.T_COMMA:
					res.register_advancement()
					self.advance()

					if self.current_tok.type != token.T_IDENTIFIER:
						return res.failure(errors.InvalidSyntaxError(
							self.current_tok.pos_start, self.current_tok.pos_end,
							f"Expected identifier"
						))

					optional_arg_name_tokens.append(self.current_tok)
					res.register_advancement()
					self.advance()

					if self.current_tok.type != token.T_EQ:
						return res.failure(errors.InvalidSyntaxError(
							self.current_tok.pos_start, self.current_tok.pos_end,
							f"Expected ="
						))

					res.register_advancement()
					self.advance()

					value = res.register(self.atom())
					if res.error: return res

					optional_arg_values_tokens.append(value)	
      
			if self.current_tok.type != token.T_RPAREN:
				return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected ',' or ')'"
				))

		else:
			if self.current_tok.type != token.T_RPAREN:
				return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected identifier or ')'"
				))

		res.register_advancement()
		self.advance()

		if self.current_tok.type == token.T_ARROW:
			res.register_advancement()
			self.advance()

			body = res.register(self.expr())
			if res.error: return res

			return res.success(nodes.FunctionDefNode(
				var_name_tok,
				arg_name_toks,
				optional_arg_name_tokens,
				optional_arg_values_tokens,
				body,
				True
			))

		if self.current_tok.type != token.T_LCURLY:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected '{'"
			))

		res.register_advancement()
		self.advance()
    
		if self.current_tok.type != token.T_NEWLINE:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				f"Expected '->' or a new line"
			))

		res.register_advancement()
		self.advance()

		body = res.register(self.statements())
		if res.error: return res

		if self.current_tok.type != token.T_RCURLY:
			return res.failure(errors.InvalidSyntaxError(
				self.current_tok.pos_start, self.current_tok.pos_end,
				"Expected '}'"
			))

		res.register_advancement()
		self.advance()
		
		return res.success(nodes.FunctionDefNode(
			var_name_tok,
			arg_name_toks,
			optional_arg_name_tokens,
			optional_arg_values_tokens,
			body,
			False
		))



	###################################

	def bin_op(self, func_a, ops, func_b=None):
		if func_b == None:
			func_b = func_a
		
		res = ParseResult()
		left = res.register(func_a())
		if res.error: return res

		while self.current_tok.type in ops or (self.current_tok.type, self.current_tok.value) in ops:
			op_tok = self.current_tok
			res.register_advancement()
			self.advance()
			right = res.register(func_b())
			if res.error: return res
			left = nodes.BinOpNode(left, op_tok, right)

		return res.success(left)
