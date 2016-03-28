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
                }
            }
        })
    })



    .controller("productPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){



        console.log("product controller retrieved the person", Person.d)
        var doi = $routeParams.id // all IDs are DOIs for now.
        var product = _.findWhere(Person.d.products, {doi: doi})

        $scope.person = Person.d
        $scope.sources = product.sources
        $scope.doi = doi
        $scope.posts = product.posts
        $scope.tweeters = product.tweeters
        $scope.product = product
        $scope.badges = _.filter(Person.d.badges, function(badge){
            return badge.is_for_products && _.contains(badge.dois, doi)
        })

        console.log("$scope.product", $scope.product)


        // workspace. copied from the person page.
        $scope.workspace = "achievements"
        $scope.viewThisSource = null
        $scope.setWorkspace = function(workspaceName, viewThisSource){
            console.log("setWorkspace", workspaceName, viewThisSource)
            if (viewThisSource == "twitter"){
                $scope.workspace = "twitter"
                console.log("setting workspace to twitter!")
                return true
            }
            $scope.workspace = workspaceName
            $scope.viewThisSource = viewThisSource
        }



        $scope.altmetricScoreModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title('The Altmetric.com score')
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                //.targetEvent(ev)
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };


    })



