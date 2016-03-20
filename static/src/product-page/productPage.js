angular.module('productPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/product/:namespace/:id*', {
            templateUrl: 'product-page/product-page.tpl.html',
            controller: 'productPageCtrl'
            ,
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                },
                badgesResp: function($http, $route, BadgeDefs){
                    console.log("loaded the badge defs in the route def")
                    return BadgeDefs.load()
                }
            }
        })
    })



    .controller("productPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){



        console.log("loaded the product controller")
        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs
        console.log("retrieved the person", $scope.person)

        var doi = $routeParams.id // all IDs are DOIs for now.
        $scope.product = _.findWhere(Person.d.products, {doi: doi})
        console.log("$scope.product", $scope.product)



        //
        //
        //
        //var badgesWithConfigs = Person.getBadgesWithConfigs(BadgeDefs.d)
        //
        //var groupedByLevel = _.groupBy(badgesWithConfigs, "level")
        //
        //// ok the badge columns are all set up, put in scope now.
        //$scope.badgeCols = [
        //    {level: "gold", list: groupedByLevel.gold},
        //    {level: "silver", list: groupedByLevel.silver},
        //    {level: "bronze", list: groupedByLevel.bronze}
        //]










    })



