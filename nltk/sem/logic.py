# Natural Language Toolkit: Logic
#
# Author: Daniel H. Garrette <dhgarrette@gmail.com>
#
# URL: <http://www.nltk.org>
# For license information, see LICENSE.TXT

"""
A version of first order predicate logic, built on top of the untyped lambda calculus.
"""

from nltk.internals import Counter
from nltk.tokenize.simple import WhitespaceTokenizer

n = 1

_counter = Counter()

class Expression(object):
    def __call__(self, other):
        return self.applyto(other)
    
    def applyto(self, other):
        if not isinstance(other, list):
            other = [other]
        return ApplicationExpression(self, other)
    
    def __neg__(self):
        return NegatedExpression(self)
    
    def negate(self):
        return -self
    
    def __eq__(self, other):
        raise NotImplementedError()
    
    def tp_equals(self, other, prover_name='tableau'):
        """Pass the expression (self <-> other) to the theorem prover.   
        If the prover says it is valid, then the self and other are equal."""
        assert isinstance(other, Expression)
        
        from nltk.inference import inference
        bicond = IffExpression(self.simplify(), other.simplify())
        prover = inference.get_prover(bicond, prover_name=prover_name)
        return prover.prove()

    def __hash__(self):
        return hash(repr(self))
    
    def unique_variable(self):
        return VariableExpression('z' + str(_counter.get()))

    def __repr__(self):
        return self.__class__.__name__ + ': ' + str(self)

class ApplicationExpression(Expression):
    """
    @param function: C{Expression}, for the function expression
    @param args: C{list} of C{Expression}, for the arguments   
    """
    def __init__(self, function, args):
        self.function = function
        self.args = args
        
    def simplify(self):
        accum = self.function.simplify()

        if isinstance(accum, LambdaExpression):
            for arg in self.args:
                if isinstance(accum, LambdaExpression):
                    accum = accum.term.replace(accum.variable, arg.simplify()).simplify()
                else:
                    accum = self.__class__(accum, [arg.simplify()])
            return accum
        else:
            return self.__class__(accum, [arg.simplify() for arg in self.args])
        
    def replace(self, variable, expression, replace_bound=False):
        return self.__class__(self.function.replace(variable, expression, replace_bound),
                              [arg.replace(variable, expression, replace_bound)
                               for arg in self.args])
        
    def free(self):
        accum = self.function.free()
        for arg in self.args:
            accum |= arg.free()
        return accum
    
    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
                self.function == other.function and self.args == other.args 

    def __str__(self):
        function = str(self.function)

        if isinstance(self.function, LambdaExpression):
            if isinstance(self.function.term, ApplicationExpression):
                if not isinstance(self.function.term.function, VariableExpression):
                    function = Tokens.OPEN + function + Tokens.CLOSE
            elif not isinstance(self.function.term, BooleanExpression):
                function = Tokens.OPEN + function + Tokens.CLOSE
        elif isinstance(self.function, ApplicationExpression):
            function = Tokens.OPEN + function + Tokens.CLOSE
                
        return function + Tokens.OPEN + \
               ','.join([str(arg) for arg in self.args]) + Tokens.CLOSE

class VariableExpression(Expression):
    """
    @param name: C{str}, for the variable name
    """
    def __init__(self, name):
        self.name = name

    def simplify(self):
        return self

    def replace(self, variable, expression, replace_bound=False):
        if self == variable:
            return expression
        else:
            return self
    
    def free(self):
        return set([self])
    
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.name == other.name
        
    def __str__(self):
        return self.name
    
class VariableBinderExpression(Expression):
    def __init__(self, variable, term):
        """
        @param variable: C{VariableExpression}, for the variable
        @param term: C{Expression}, for the term
        """
        self.variable = variable
        self.term = term

    def simplify(self):
        return self.__class__(self.variable, self.term.simplify())

    def replace(self, variable, expression, replace_bound=False):
        #if the bound variable is the thing being replaced
        if self.variable == variable:
            if replace_bound: 
                return self.__class__(expression, 
                                      self.term.replace(variable, expression, True))
            else: 
                return self
                
        else:
            # if the bound variable appears in the expression, then it must
            # be alpha converted to avoid a conflict
            if self.variable in expression.free():
                self = self.alpha_convert(self.unique_variable())
                
            #replace in the term
            return self.__class__(self.variable,
                                  self.term.replace(variable, expression, replace_bound))

    def alpha_convert(self, newvar):
        """Rename all occurrences of the variable introduced by this variable
        binder in the expression to @C{newvar}."""
        return self.__class__(newvar, self.term.replace(self.variable, newvar, True))

    def free(self):
        return self.term.free() - set([self.variable])

    def __eq__(self, other):
        r"""Defines equality modulo alphabetic variance.
        If we are comparing \x.M  and \y.N, then check equality of M and N[x/y]."""
        if isinstance(other, self.__class__):
            if self.variable == other.variable:
                return self.term == other.term
            else:
                # Comparing \x.M  and \y.N.  Relabel y in N with x and continue.
                return self.term == other.term.replace(other.variable, self.variable)
        else:
            return False

class LambdaExpression(VariableBinderExpression):
    def __str__(self):
        return Tokens.LAMBDA[n] + str(self.variable) + Tokens.DOT[n] + str(self.term)

class QuantifiedExpression(VariableBinderExpression):
    def __str__(self):
        return self.getPredicate() + ' ' + str(self.variable) + Tokens.DOT[n] + str(self.term)
        
class ExistsExpression(QuantifiedExpression):
    def getPredicate(self):
        return Tokens.EXISTS[n]

class AllExpression(QuantifiedExpression):
    def getPredicate(self):
        return Tokens.ALL[n]

class NegatedExpression(Expression):
    def __init__(self, term):
        self.term = term
        
    def simplify(self):
        return self

    def replace(self, variable, expression, replace_bound=False):
        return self.__class__(self.term.replace(variable, expression, replace_bound))

    def free(self):
        return self.term.free()

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.term == other.term

    def __str__(self):
        return Tokens.NOT[n] + str(self.term)
        
class BooleanExpression(Expression):
    def __init__(self, first, second):
        self.first = first
        self.second = second
    
    def simplify(self):
        return self.__class__(self.first.simplify(), self.second.simplify())

    def replace(self, variable, expression, replace_bound=False):
        return self.__class__(self.first.replace(variable, expression, replace_bound),
                              self.second.replace(variable, expression, replace_bound))

    def free(self):
        return self.first.free() | self.second.free()

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
                and self.first == other.first and self.second == other.second

    def __str__(self):
        return Tokens.OPEN + str(self.first) + ' ' + self.getOp() + ' ' + str(self.second) + Tokens.CLOSE
        
class AndExpression(BooleanExpression):
    def getOp(self):
        return Tokens.AND[n]

class OrExpression(BooleanExpression):
    def getOp(self):
        return Tokens.OR[n]

class ImpExpression(BooleanExpression):
    def getOp(self):
        return Tokens.IMP[n]

class IffExpression(BooleanExpression):
    def getOp(self):
        return Tokens.IFF[n]

class EqualityExpression(BooleanExpression):
    def getOp(self):
        return Tokens.EQ[n]

class Tokens:
    # Syntaxes
    OLD_NLTK = 0
    NEW_NLTK = 1
    PROVER9  = 2
    
    
    LAMBDA = ['\\', '\\', '\\']
    
    #Quantifiers
    EXISTS = ['some', 'exists', 'exists']
    ALL = ['all', 'all', 'all']
    
    #Punctuation
    DOT = ['.', '.', ' ']
    OPEN = '('
    CLOSE = ')'
    COMMA = ','
    
    #Operations
    NOT = ['not', '-', '-']
    AND = ['and', '&', '&']
    OR = ['or', '|', '|']
    IMP = ['implies', '->', '->']
    IFF = ['iff', '<->', '<->']
    EQ = ['=', '=', '=']
    
    #Collection of tokens
    BOOLS = AND + OR + IMP + IFF
    BINOPS = BOOLS + EQ
    QUANTS = EXISTS + ALL
    PUNCT = [DOT[0], OPEN, CLOSE, COMMA]
    
    TOKENS = BINOPS + QUANTS + LAMBDA + PUNCT + NOT
    
    #Special
    SYMBOLS = LAMBDA + PUNCT + [AND[1], OR[1], NOT[1], IMP[1], IFF[1]] + EQ 

class LogicParser:
    """A lambda calculus expression parser."""

    def __init__(self):
        """
        @param data: C{str}, a string to parse
        """
        self._currentIndex = 0
        self._buffer = []

    def parse(self, data):
        """
        Parse the expression.

        @param data: C{str} for the input to be parsed
        @returns: a parsed Expression
        """
        self._currentIndex = 0
        self._buffer = WhitespaceTokenizer().tokenize(self.process(data))
        result = self.parse_Expression()
        if self.inRange(0):
            raise UnexpectedTokenException(self.token(0))
        return result

    def process(self, data):
        """Put whitespace between symbols to make parsing easier"""
        out = ''
        tokenTrie = StringTrie(self.get_all_symbols())
        while data:
            st = tokenTrie
            c = data[0]
            token = ''
            while c in st:
                token += c
                st = st[c]
                if len(data) > len(token):
                    c = data[len(token)]
                else:
                    break
            if token:
                out += ' '+token+' '
                data = data[len(token):]
            else:
                out += c
                data = data[1:]
        return out

    def get_all_symbols(self):
        """This method exists to be overridden"""
        return Tokens.SYMBOLS

    def inRange(self, location):
        """Return TRUE if the given location is within the buffer"""
        return self._currentIndex+location < len(self._buffer)

    def token(self, location=None):
        """Get the next waiting token.  If a location is given, then 
        return the token at currentIndex+location without advancing
        currentIndex; setting it gives lookahead/lookback capability."""
        try:
            if location == None:
                tok = self._buffer[self._currentIndex]
                self._currentIndex += 1
            else:
                assert isinstance(location,int) 
                tok = self._buffer[self._currentIndex+location]
            return tok
        except IndexError:
            raise UnexpectedTokenException, 'The given location is out of range'

    def isvariable(self, tok):
        return tok not in Tokens.TOKENS
    
    def parse_Expression(self):
        """Parse the next complete expression from the stream and return it."""
        tok = self.token()
        
        if self.isvariable(tok):
            return self.handle_variable(tok)
        
        elif tok in Tokens.NOT:
            #it's a negated expression
            return self.make_NegatedExpression(self.parse_Expression())
        
        elif tok in Tokens.LAMBDA:
            return self.handle_lambda(tok)
            
        elif tok in Tokens.QUANTS:
            return self.handle_quant(tok)
            
        elif tok == Tokens.OPEN:
            return self.handle_open(tok)
        
        else:
            raise UnexpectedTokenException(tok)
        
    def make_NegatedExpression(self, expression):
        return NegatedExpression(expression)
        
    def handle_variable(self, tok):
        #It's either: 1) a predicate expression: sees(x,y)
        #             2) an application expression: P(x)
        #             3) a solo variable: john OR x
        if self.inRange(0) and self.token(0) == Tokens.OPEN:
            #The predicate has arguments
            self.token() #swallow the Open Paren
            
            #gather the arguments
            args = []
            if self.token(0) != Tokens.CLOSE:
                args.append(self.parse_Expression())
                while self.token(0) == Tokens.COMMA:
                    self.token() #swallow the comma
                    args.append(self.parse_Expression())
            self.assertToken(self.token(), Tokens.CLOSE)
            
            expression = self.make_ApplicationExpression(self.make_VariableExpression(tok), args)
            return self.attempt_BooleanExpression(expression)
        else:
            #The predicate has no arguments: it's a solo variable
            return self.make_VariableExpression(tok)
        
    def handle_lambda(self, tok):
        # Expression is a lambda expression
        
        vars = [self.make_VariableExpression(self.token())]
        while True:
            while self.isvariable(self.token(0)):
                # Support expressions like: \x y.M == \x.\y.M
                vars.append(self.make_VariableExpression(self.token()))
            self.assertToken(self.token(), Tokens.DOT)
            
            if self.token(0) in Tokens.LAMBDA:
                #if it's directly followed by another lambda, keep the lambda 
                #expressions together, so that \x.\y.M == \x y.M
                self.token() #swallow the lambda symbol
            else:
                break
        
        accum = self.parse_Expression()
        while vars:
            accum = self.make_LambdaExpression(vars.pop(), accum)

        accum = self.attempt_ApplicationExpression(accum)
        return self.attempt_BooleanExpression(accum)
        
    def get_QuantifiedExpression_factory(self, tok):
        """This method serves as a hook for other logic parsers that
        have different quantifiers"""
        factory = None
        if tok in Tokens.EXISTS:
            factory = ExistsExpression
        elif tok in Tokens.ALL:
            factory = AllExpression
        else:
            self.assertToken(tok, Tokens.EXISTS + Tokens.ALL)
        return factory

    def handle_quant(self, tok):
        # Expression is a quantified expression: some x.M
        factory = self.get_QuantifiedExpression_factory(tok)

        vars = [self.token()]
        while self.isvariable(self.token(0)):
            # Support expressions like: some x y.M == some x.some y.M
            vars.append(self.token())
        self.assertToken(self.token(), Tokens.DOT)

        term = self.parse_Expression()
        accum = factory(self.make_VariableExpression(vars.pop()), term)
        while vars:
            accum = factory(self.make_VariableExpression(vars.pop()), accum)
        
        return self.attempt_BooleanExpression(accum)
        
    def handle_open(self, tok):
        #Expression is in parens
        newExpression = self.attempt_BooleanExpression(self.parse_Expression())
        self.assertToken(self.token(), Tokens.CLOSE)
        return self.attempt_ApplicationExpression(newExpression)
        
    def attempt_BooleanExpression(self, expression):
        """Attempt to make a boolean expression.  If the next token is a boolean 
        operator, then a BooleanExpression will be returned.  Otherwise, the 
        parameter will be returned."""
        if self.inRange(0):
            factory = self.get_BooleanExpression_factory()
            if factory: #if a factory was returned
                self.token() #swallow the operator
                return self.make_BooleanExpression(factory, expression, self.parse_Expression())
        #otherwise, no boolean expression can be created
        return expression
    
    def get_BooleanExpression_factory(self):
        """This method serves as a hook for other logic parsers that
        have different boolean operators"""
        factory = None
        op = self.token(0)
        if op in Tokens.AND:
            factory = AndExpression
        elif op in Tokens.OR:
            factory = OrExpression
        elif op in Tokens.IMP:
            factory = ImpExpression
        elif op in Tokens.IFF:
            factory = IffExpression
        elif op in Tokens.EQ:
            factory = EqualityExpression
        return factory
    
    def make_BooleanExpression(self, type, first, second):
        """This method exists to be overridden by parsers
        with more complex logic for creating BooleanExpressions"""
        return type(first, second)
        
    def attempt_ApplicationExpression(self, expression):
        """Attempt to make an application expression.  The next tokens are
        a list of arguments in parens, then the argument expression is a
        function being applied to the arguments.  Otherwise, return the
        argument expression."""
        if self.inRange(0) and self.token(0) == Tokens.OPEN:
            if not isinstance(expression, LambdaExpression) and \
               not isinstance(expression, ApplicationExpression):
                raise ParseException("The function '" + str(expression) + 
                                     "' is not a Lambda Expression or an Application Expression, so it may not take arguments")
        
            self.token() #swallow then open paren
            if isinstance(expression, LambdaExpression):
                accum = expression
                if self.token(0) != Tokens.CLOSE:
                    accum = self.make_ApplicationExpression(accum, [self.parse_Expression()])
                    while self.token(0) == Tokens.COMMA:
                        self.token() #swallow the comma
                        accum = self.make_ApplicationExpression(accum, [self.parse_Expression()])
                self.assertToken(self.token(), Tokens.CLOSE)
                retEx = accum
            else:
                args = []
                if self.token(0) != Tokens.CLOSE:
                    args.append(self.parse_Expression())
                    while self.token(0) == Tokens.COMMA:
                        self.token() #swallow the comma
                        args.append(self.parse_Expression())
                self.assertToken(self.token(), Tokens.CLOSE)
                retEx = self.make_ApplicationExpression(expression, args)
            return self.attempt_ApplicationExpression(retEx) 
        else:
            return expression

    def make_ApplicationExpression(self, function, args):
        return ApplicationExpression(function, args)
    
    def make_VariableExpression(self, name):
        return VariableExpression(name)
    
    def make_LambdaExpression(self, variable, term):
        return LambdaExpression(variable, term)
    
    def assertToken(self, tok, expected):
        if isinstance(expected, list):
            if tok not in expected:
                raise UnexpectedTokenException(tok, expected)
        else:
            if tok != expected:
                raise UnexpectedTokenException(tok, expected)

    def __repr__(self):
        if self.inRange(0):
            return 'Next token: ' + self.token(0)
        else:
            return 'No more tokens'

            
class StringTrie(dict):
    LEAF = "<leaf>" 

    def __init__(self, strings=None):
        if strings:
            for string in strings:
                self.insert(string)
    
    def insert(self, string):
        if len(string):
            k = string[0]
            if k not in self:
                self[k] = StringTrie()
            self[k].insert(string[1:])
        else:
            #mark the string is complete
            self[StringTrie.LEAF] = None 

class ParseException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class UnexpectedTokenException(Exception):
    def __init__(self, tok, expected=None):
        if expected:
            Exception.__init__(self, "parse error, unexpected token: %s.  Expected token: %s" % (tok, expected))
        else:
            Exception.__init__(self, "parse error, unexpected token: %s" % tok)
        
        
###############################
#TODO: DELETE ALL
################################
class Error: pass
class Variable: pass
def is_indvar(): pass
class SubstituteBindingsI: pass
class Operator: pass

def demo():
    lp = LogicParser()
    print '='*20 + 'Test parser' + '='*20
    print lp.parse(r'john')
    print lp.parse(r'man(x)')
    print lp.parse(r'-man(x)')
    print lp.parse(r'(man(x) & tall(x) & walks(x))')
    print lp.parse(r'exists x.(man(x) & tall(x))')
    print lp.parse(r'\x.man(x)')
    print lp.parse(r'\x.man(x)(john)')
    print lp.parse(r'\x y.sees(x,y)')
    print lp.parse(r'\x  y.sees(x,y)(a,b)')
    print lp.parse(r'(\x.exists y.walks(x,y))(x)')
    print lp.parse(r'exists x.(x = john)')
    print lp.parse(r'\P Q.exists x.(P(x) & Q(x))')
    
    print '='*20 + 'Test simplify' + '='*20
    print lp.parse(r'\x.\y.sees(x,y)(john)(mary)').simplify()
    print lp.parse(r'\x.\y.sees(x,y)(john, mary)').simplify()
    print lp.parse(r'exists x.(man(x) & (\x.exists y.walks(x,y))(x))').simplify()
    print lp.parse(r'((\P.\Q.exists x.(P(x) & Q(x)))(\x.dog(x)))(\x.bark(x))').simplify()
    
    print '='*20 + 'Test alpha conversion and binder expression equality' + '='*20
    e1 = lp.parse('exists x.P(x)')
    print e1
    e2 = e1.alpha_convert(VariableExpression('z'))
    print e2
    print e1 == e2

if __name__ == '__main__':
    demo()

    lp = LogicParser()
    print lp.parse(r'\x.man(x) john')
    print lp.parse(r'\x.man(x)(john)')
    print ''
    print lp.parse(r'\P.P(x) \x.man(x)')
    print lp.parse(r'\P.P(x)(\x.man(x))')
    print ''
    print lp.parse(r'exists b.a(b) & a(b)')
    print lp.parse(r'(exists b.a(b)) & a(b)')
    print ''
    print lp.parse(r'\x.(P(x))(y)') 
    print lp.parse(r'(\x.P(x))(y)" instead of "\x.(P(x)(y))')

